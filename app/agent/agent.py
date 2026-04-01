from sqlalchemy.orm import Session

from app.agent.router import extract_order_id, extract_reason, route_message
from app.agent.schemas import AgentResponse, RoutedIntent
from app.agent.state import clear_state, get_or_create_state, save_state
from app.tools.orders import cancel_order, get_order, request_refund

import logging


def snapshot_state(state) -> dict:
    return {
        "pending_intent": state.pending_intent,
        "order_id": state.order_id,
        "reason": state.reason,
        "awaiting_confirmation": state.awaiting_confirmation,
        "last_action": state.last_action,
    }


def map_guardrail(message: str) -> str | None:
    mapping = {
        "Order not found.": "order_not_found",
        "Shipped orders cannot be cancelled.": "shipped_order_non_cancellable",
        "Delivered orders cannot be cancelled.": "delivered_order_non_cancellable",
        "Order is already cancelled.": "order_already_cancelled",
        "Refunded orders cannot be cancelled.": "refunded_order_non_cancellable",
        "Refund reason is required.": "refund_reason_required",
        "Only delivered orders are eligible for refund requests.": "delivered_order_required_for_refund",
        "A refund has already been requested for this order.": "refund_already_requested",
        "Order has already been refunded.": "order_already_refunded",
        "Cancelled orders cannot be refunded.": "cancelled_order_non_refundable",
    }
    return mapping.get(message)


def log_kv(logs: list[str], key: str, value) -> None:
    logs.append(f"{key}={value}")


def normalize_route_result(route_result) -> tuple[RoutedIntent, str]:
    if isinstance(route_result, tuple):
        return route_result
    return route_result, "rule"


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)


def handle_agent_message(user_id: str, message: str, db: Session) -> AgentResponse:
    logs: list[str] = []
    state = get_or_create_state(user_id)
    state_before = state.to_dict()

    text = message.strip()
    lowered = text.lower()

    log_kv(logs, "message_received", text)

    # ──────────────────────────────────────────
    # 1) Awaiting confirmation
    # ──────────────────────────────────────────
    if state.awaiting_confirmation:
        log_kv(logs, "workflow_state", "awaiting_confirmation")

        # FIX: capture pending_order_id here, before any branching,
        # so it's available in the "no" and ambiguous response paths too.
        pending_order_id = state.order_id

        if lowered in {"yes", "confirm", "please do", "go ahead"}:
            if state.pending_intent == "cancel_order" and pending_order_id:
                result = cancel_order(pending_order_id, db)
                guardrail = map_guardrail(result["message"])

                clear_state(user_id)
                state_after = state.to_dict()

                logger.info(
                    f"AGENT | intent=cancel_order"
                    f" | state={'action_completed' if result['success'] else 'action_blocked'}"
                    f" | action=cancel_order"
                    f" | result={'completed' if result['success'] else 'blocked'}"
                    f" | guardrail={guardrail}"
                    f" | order_id={pending_order_id}"
                )

                return AgentResponse(
                    response=result["message"],
                    success=result["success"],
                    action_taken="cancel_order" if result["success"] else None,
                    intent="cancel_order",
                    workflow_state="action_completed" if result["success"] else "action_blocked",
                    state_before=state_before,
                    state_after=state_after,
                    action_attempted="cancel_order",
                    action_result="completed" if result["success"] else "blocked",
                    guardrail_triggered=guardrail,
                    extracted={"order_id": pending_order_id},
                    logs=logs + [
                        "confirmation.accepted",
                        "tool_called=cancel_order",
                        f"tool_success={str(result['success']).lower()}",
                    ],
                )

            # Confirmed but no valid pending action
            clear_state(user_id)
            state_after = state.to_dict()

            logger.info(
                f"AGENT | intent=unknown"
                f" | action=None"
                f" | result=None"
                f" | guardrail=None"
                f" | order_id={pending_order_id}"
            )

            return AgentResponse(
                response="Confirmation was received, but no valid pending action was found.",
                success=False,
                action_taken=None,
                intent=None,
                workflow_state="confirmation_invalid",
                state_before=state_before,
                state_after=state_after,
                action_attempted=None,
                action_result="not_attempted",
                guardrail_triggered=None,
                extracted={},
                logs=logs + ["confirmation.invalid_no_pending_action"],
            )

        if lowered in {"no", "stop", "don't", "cancel"}:
            clear_state(user_id)
            state_after = state.to_dict()

            logger.info(
                f"AGENT | intent=cancel_order"
                f" | state=confirmation_declined"
                f" | action=cancel_order"
                f" | result=declined"
                f" | guardrail=None"
                f" | order_id={pending_order_id}"
            )

            return AgentResponse(
                response="No problem — your order has not been cancelled.\n\nI did not take any action.",
                success=True,
                action_taken=None,
                intent="cancel_order",
                workflow_state="confirmation_declined",
                state_before=state_before,
                state_after=state_after,
                action_attempted="cancel_order",
                action_result="not_attempted",
                guardrail_triggered=None,
                extracted={},
                logs=logs + ["confirmation.declined"],
            )

        # Ambiguous response while awaiting confirmation
        state_after = state.to_dict()

        logger.info(
            f"AGENT | intent={state.pending_intent}"
            f" | state=awaiting_confirmation"
            f" | action=None"
            f" | guardrail=None"
            f" | order_id={pending_order_id}"
        )

        return AgentResponse(
            response='Please reply with "yes" to confirm or "no" to cancel the action.',
            success=False,
            action_taken=None,
            intent=state.pending_intent,
            workflow_state="awaiting_confirmation",
            state_before=state_before,
            state_after=state_after,
            action_attempted=state.pending_intent,
            action_result="awaiting_input",
            guardrail_triggered=None,
            extracted={"order_id": pending_order_id},
            logs=logs + ["confirmation.invalid_response"],
        )

    # ──────────────────────────────────────────
    # 2) Pending refund — slot filling
    # ──────────────────────────────────────────
    if state.pending_intent == "request_refund":
        log_kv(logs, "workflow_state", "pending_refund")

        extracted_order_id = extract_order_id(text)
        extracted_reason = extract_reason(text)

        if extracted_order_id and not state.order_id:
            state.order_id = extracted_order_id
            save_state(state)
            log_kv(logs, "state_order_id_filled", extracted_order_id)

        if extracted_reason and not state.reason:
            state.reason = extracted_reason
            save_state(state)
            log_kv(logs, "state_reason_filled", True)

        missing_fields: list[str] = []
        if not state.order_id:
            missing_fields.append("order_id")
        if not state.reason:
            missing_fields.append("reason")

        if missing_fields:
            state_after = state.to_dict()
            log_kv(logs, "missing_fields", ",".join(missing_fields))

            logger.info(
                f"AGENT | intent=request_refund"
                f" | state=awaiting_missing_fields"
                f" | action=None"
                f" | guardrail=None"
                f" | order_id={state.order_id}"
            )

            return AgentResponse(
                response=(
                    "To request a refund, I need your order ID and the reason for the refund."
                    if len(missing_fields) == 2
                    else f"I just need one more thing: {missing_fields[0]}."
                ),
                success=False,
                action_taken=None,
                intent="request_refund",
                workflow_state="awaiting_missing_fields",
                state_before=state_before,
                state_after=state_after,
                action_attempted="request_refund",
                action_result="awaiting_input",
                guardrail_triggered=None,
                extracted={
                    "order_id": state.order_id,
                    "reason": state.reason,
                },
                missing_fields=missing_fields,
                logs=logs,
            )

        result = request_refund(state.order_id, state.reason, db)
        guardrail = map_guardrail(result["message"])

        completed_order_id = state.order_id
        completed_reason = state.reason

        clear_state(user_id)
        state_after = state.to_dict()

        logger.info(
            f"AGENT | intent=request_refund"
            f" | state={'action_completed' if result['success'] else 'action_blocked'}"
            f" | action=request_refund"
            f" | result={'completed' if result['success'] else 'blocked'}"
            f" | guardrail={guardrail}"
            f" | order_id={completed_order_id}"
        )

        return AgentResponse(
            response=result["message"],
            success=result["success"],
            action_taken="request_refund" if result["success"] else None,
            intent="request_refund",
            workflow_state="action_completed" if result["success"] else "action_blocked",
            state_before=state_before,
            state_after=state_after,
            action_attempted="request_refund",
            action_result="completed" if result["success"] else "blocked",
            guardrail_triggered=guardrail,
            extracted={
                "order_id": completed_order_id,
                "reason": completed_reason,
            },
            logs=logs + [
                "tool_called=request_refund",
                f"tool_success={str(result['success']).lower()}",
            ],
        )

    # ──────────────────────────────────────────
    # 3) Fresh routing
    # ──────────────────────────────────────────
    route_result = route_message(text)
    routed, routing_source = normalize_route_result(route_result)

    log_kv(logs, "routing_source", routing_source)
    log_kv(logs, "intent", routed.intent)
    log_kv(logs, "order_id", routed.order_id)
    log_kv(logs, "reason_present", str(routed.reason is not None).lower())

    # ── Unknown intent ──
    if routed.intent == "unknown":
        state_after = state.to_dict()

        logger.info(
            "AGENT | intent=unknown | state=unable_to_route | action=None | guardrail=None"
        )

        return AgentResponse(
            response=(
                "I can help with:\n"
                "- checking an order\n"
                "- cancelling an order\n"
                "- requesting a refund\n\n"
                "Try something like:\n"
                "ORD-1002\n"
                "Cancel my order ORD-1001\n"
                "I want a refund for ORD-1003"
            ),
            success=False,
            action_taken=None,
            intent="unknown",
            workflow_state="unable_to_route",
            state_before=state_before,
            state_after=state_after,
            action_attempted=None,
            action_result="not_attempted",
            guardrail_triggered=None,
            extracted={},
            logs=logs,
        )

    # ── Get order ──
    if routed.intent == "get_order":
        if not routed.order_id:
            state_after = state.to_dict()
            return AgentResponse(
                response="Please provide your order ID so I can look it up.",
                success=False,
                action_taken=None,
                intent="get_order",
                workflow_state="awaiting_missing_fields",
                state_before=state_before,
                state_after=state_after,
                action_attempted="get_order",
                action_result="awaiting_input",
                guardrail_triggered=None,
                extracted={},
                missing_fields=["order_id"],
                logs=logs + ["missing_fields=order_id"],
            )

        result = get_order(routed.order_id, db)

        if not result["success"]:
            state_after = state.to_dict()
            guardrail = map_guardrail(result["message"])

            return AgentResponse(
                response=result["message"],
                success=False,
                action_taken=None,
                intent="get_order",
                workflow_state="action_blocked",
                state_before=state_before,
                state_after=state_after,
                action_attempted="get_order",
                action_result="blocked",
                guardrail_triggered=guardrail,
                extracted={"order_id": routed.order_id},
                logs=logs + [
                    "tool_called=get_order",
                    "tool_success=false",
                ],
            )

        order = result["order"]
        item_name = order["item_name"].replace("_", " ")
        state_after = state.to_dict()

        return AgentResponse(
            response=(
                f"Order {order['order_id']} is currently {order['status']}.\n\n"
                f"Item: {item_name}\n"
                f"Total: ${order['amount']:.2f}\n\n"
                "If you need help with this order, you can ask to cancel it or request a refund."
            ),
            success=True,
            action_taken="get_order",
            intent="get_order",
            workflow_state="lookup_completed",
            state_before=state_before,
            state_after=state_after,
            action_attempted="get_order",
            action_result="completed",
            guardrail_triggered=None,
            extracted={"order_id": routed.order_id},
            logs=logs + [
                "tool_called=get_order",
                "tool_success=true",
            ],
        )

    # ── Cancel order ──
    if routed.intent == "cancel_order":
        if not routed.order_id:
            state_after = state.to_dict()
            return AgentResponse(
                response="Please provide the order ID you want to cancel.",
                success=False,
                action_taken=None,
                intent="cancel_order",
                workflow_state="awaiting_missing_fields",
                state_before=state_before,
                state_after=state_after,
                action_attempted="cancel_order",
                action_result="awaiting_input",
                guardrail_triggered=None,
                extracted={},
                missing_fields=["order_id"],
                logs=logs + ["missing_fields=order_id"],
            )

        state.pending_intent = "cancel_order"
        state.order_id = routed.order_id
        state.awaiting_confirmation = True
        save_state(state)
        state_after = state.to_dict()

        return AgentResponse(
            response=(
                f"You're about to cancel order {routed.order_id}.\n\n"
                "Reply 'yes' to confirm or 'no' to keep the order."
            ),
            success=True,
            action_taken=None,
            intent="cancel_order",
            workflow_state="awaiting_confirmation",
            state_before=state_before,
            state_after=state_after,
            action_attempted="cancel_order",
            action_result="pending_confirmation",
            guardrail_triggered=None,
            extracted={"order_id": routed.order_id},
            logs=logs + ["state_updated=awaiting_cancel_confirmation"],
        )

    # ── Request refund ──
    if routed.intent == "request_refund":
        state.pending_intent = "request_refund"
        state.order_id = routed.order_id
        state.reason = routed.reason
        save_state(state)

        missing_fields: list[str] = []
        if not state.order_id:
            missing_fields.append("order_id")
        if not state.reason:
            missing_fields.append("reason")

        if missing_fields:
            state_after = state.to_dict()
            log_kv(logs, "missing_fields", ",".join(missing_fields))

            return AgentResponse(
                response=(
                    "To request a refund, I need your order ID and the reason for the refund."
                    if len(missing_fields) == 2
                    else f"I just need one more thing: {missing_fields[0]}."
                ),
                success=False,
                action_taken=None,
                intent="request_refund",
                workflow_state="awaiting_missing_fields",
                state_before=state_before,
                state_after=state_after,
                action_attempted="request_refund",
                action_result="awaiting_input",
                guardrail_triggered=None,
                extracted={
                    "order_id": state.order_id,
                    "reason": state.reason,
                },
                missing_fields=missing_fields,
                logs=logs,
            )

        result = request_refund(state.order_id, state.reason, db)
        guardrail = map_guardrail(result["message"])

        completed_order_id = state.order_id
        completed_reason = state.reason

        clear_state(user_id)
        state_after = state.to_dict()

        logger.info(
            f"AGENT | intent=request_refund"
            f" | state={'action_completed' if result['success'] else 'action_blocked'}"
            f" | action=request_refund"
            f" | result={'completed' if result['success'] else 'blocked'}"
            f" | guardrail={guardrail}"
            f" | order_id={completed_order_id}"
        )

        return AgentResponse(
            response=result["message"],
            success=result["success"],
            action_taken="request_refund" if result["success"] else None,
            intent="request_refund",
            workflow_state="action_completed" if result["success"] else "action_blocked",
            state_before=state_before,
            state_after=state_after,
            action_attempted="request_refund",
            action_result="completed" if result["success"] else "blocked",
            guardrail_triggered=guardrail,
            extracted={
                "order_id": completed_order_id,
                "reason": completed_reason,
            },
            logs=logs + [
                "tool_called=request_refund",
                f"tool_success={str(result['success']).lower()}",
            ],
        )

    # ── Fallback ──
    state_after = state.to_dict()
    return AgentResponse(
        response="Something went wrong while processing your request. Please try again.",
        success=False,
        action_taken=None,
        intent=None,
        workflow_state="unable_to_route",
        state_before=state_before,
        state_after=state_after,
        action_attempted=None,
        action_result="not_attempted",
        guardrail_triggered=None,
        extracted={},
        logs=logs + ["routing_fell_through=true"],
    )