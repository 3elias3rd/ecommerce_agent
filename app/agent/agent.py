from sqlalchemy.orm import Session

from app.agent.router import route_message
from app.agent.schemas import AgentResponse
from app.agent.router import extract_order_id, extract_reason, route_message
from app.agent.schemas import AgentResponse, RoutedIntent
from app.agent.state import clear_state, get_or_create_state
from app.tools.orders import cancel_order, get_order, request_refund

import logging

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)


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


def handle_agent_message(user_id: str, message: str, db: Session) -> AgentResponse:
    logs: list[str] = []
    state = get_or_create_state(user_id)

    text = message.strip()
    lowered = text.lower()

    logs.append(f"received_message={text}")

    # -------------------------------
    # 1. Awaiting confirmation
    # -------------------------------
    if state.awaiting_confirmation:
        logs.append("state-awaiting_confirmation")

        if lowered in {"yes", "confirm", "please do", "go ahead"}:
            if state.pending_intent == "cancel_order" and state.order_id:
                pending_order_id = state.order_id
                result = cancel_order(pending_order_id, db)
                clear_state (user_id)
                order_id = state.order_id
                result = cancel_order(order_id, db)
                guardrail = map_guardrail(result["message"])

                clear_state(user_id)
                state_after = get_or_create_state(user_id).to_dict()

                logger.info(
                    f"AGENT | intent=cancel_order | state={'action_completed' if result['success'] else 'action_blocked'} "
                    f"| action=cancel_order | result={'completed' if result['success'] else 'blocked'} "
                    f"| guardrail={guardrail} | order_id={order_id}"
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
                    extracted={"order_id": order_id},
                    logs=logs + ["confirmation.accepted"],
                )

        if lowered in {"no", "stop", "don't", "cancel"}:
            order_id = state.order_id
                    action_taken="cancel_order",
                    success = result["success"],
                    extracted={"order_id": pending_order_id},
                    logs=logs + [f"confirmed_action=cancel_order", f"tool_result={result}."]
                )
            
            clear_state(user_id)
            return AgentResponse(
                response="Confirmation was received, but no valid pending action was found.",
                action_taken=None,
                success=False,
                extracted={},
                logs=logs + ["confirmation_failed=no_pending_action"],
            )
        
        if lowered in ("no", "stop", "dont't", "cancel"):
            clear_state(user_id)
            state_after = get_or_create_state(user_id).to_dict()

            logger.info(
                f"AGENT | intent=cancel_order | state=confirmation_declined "
                f"| action=cancel_order | result=not_attempted | order_id={order_id}"
            )

            return AgentResponse(
                response="No problem — your order has not been cancelled.\n\nI did not take any action.",
                success=True,
                response="Okay, I did not take any action.",
                action_taken=None,
                success=True,
                extracted={},
                logs=logs + ["confirmation_declined=true"]
            )

        state_after = state.to_dict()

        logger.info(
            f"AGENT | intent={state.pending_intent} | state=awaiting_confirmation | result=awaiting_input"
        )

        return AgentResponse(
            response="Please reply with 'yes' to confirm or 'no' to cancel.",
            action_taken=None,
            intent=state.pending_intent,
            workflow_state="confirmation_invalid",
            state_before=state_before,
            state_after=state_after,
            action_attempted=None,
            action_result="awaiting_input",
            guardrail_triggered=None,
            extracted={"order_id": state.order_id},
            logs=logs + ["confirmation.invalid_response"],
        )

    # -------------------------------
    # 2. Refund slot filling
    # -------------------------------
    if state.pending_intent == "request_refund":
        extracted_order_id = extract_order_id(text)
        extracted_reason = extract_reason(text)

        if extracted_order_id:
            state.order_id = extracted_order_id
        if extracted_reason:
            state.reason = extracted_reason

        missing = []
        if not state.order_id:
            missing.append("order_id")
        if not state.reason:
            missing.append("reason")

        if missing:
            state_after = state.to_dict()

            logger.info(
                f"AGENT | intent=request_refund | state=awaiting_missing_fields | missing={missing}"
            )

            return AgentResponse(
                response="I need your order ID and reason for refund."
                if len(missing) == 2
                else f"I just need: {missing[0]}",
                success=False,
                action_taken=None,
                intent="request_refund",
                workflow_state="awaiting_missing_fields",
                state_before=state_before,
                state_after=state_after,
                action_attempted=None,
                action_result="awaiting_input",
                guardrail_triggered=None,
                extracted={"order_id": state.order_id, "reason": state.reason},
                missing_fields=missing,
                logs=logs,
            )

        result = request_refund(state.order_id, state.reason, db)
        guardrail = map_guardrail(result["message"])

        order_id = state.order_id
        clear_state(user_id)
        state_after = get_or_create_state(user_id).to_dict()

        logger.info(
            f"AGENT | intent=request_refund | state={'action_completed' if result['success'] else 'action_blocked'} "
            f"| result={'completed' if result['success'] else 'blocked'} | order_id={order_id}"
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
            extracted={"order_id": order_id},
            logs=logs,
        )

    # -------------------------------
    # 3. Routing
    # -------------------------------
    routed, _ = normalize_route_result(route_message(text))

            success=False,
            extracted={},
            missing_fields=[],
            logs=logs + ["state_updated=awaiting_cancel_confirmation"],
        )
    
    routed = route_message(text)
    logs.append(f"intent={routed.intent}")
    logs.append(f"extracted_order_id={routed.order_id}")
    logs.append(f"extracted_reason={routed.reason}")

    if routed.intent == "unknown":
        state_after = state.to_dict()

        logger.info("AGENT | intent=unknown | state=unable_to_route")

        return AgentResponse(
            response="I can help with order lookup, cancellation, or refund requests. Please include an order ID.",
            action_taken=None,
            success=False,
            response="I can help with orders, cancellations, or refunds.",
            success=False,
            intent="unknown",
            workflow_state="unable_to_route",
            state_before=state_before,
            state_after=state_after,
            action_result="not_attempted",
            extracted={},
            logs=logs,
        )
    

    if routed.intent == "get_order":
        if not routed.order_id:
            return AgentResponse(
                response="Please provide your order ID so I can look it up.",
                action_taken=None,
                success=False,
                extracted={},
                missing_fields=["order_id"],
                logs=logs + ["missing_field=order_id"],
            )
        
        result = get_order(routed.order_id, db)
        if not result["success"]:
            return AgentResponse(
                response=result["message"],
                action_taken="get_order",
                success=False,
                extracted={"order_id: routed.order_id"},
                logs=logs + [f"tool_result={result}"],
            )
        
        order = result["order"]

        state_after = state.to_dict()

        logger.info(f"AGENT | intent=get_order | result={result['success']}")

        return AgentResponse(
            response=(
                f"Order{order ['order_id']} is currently {order['status']}. "
                f"item: {order['item_name']}. Amount: ${order['amount']}"
            ),
            action_taken="get_order",
            success=True,
            response=result["message"] if not result["success"] else "Order found.",
            success=result["success"],
            intent="get_order",
            workflow_state="lookup_completed" if result["success"] else "action_blocked",
            state_before=state_before,
            state_after=state_after,
            action_attempted="get_order",
            action_result="completed" if result["success"] else "blocked",
            extracted={"order_id": routed.order_id},
            logs=logs + [f"tool_result={result}"],
            logs=logs,
        )
    

    if routed.intent == "cancel_order":
        if not routed.order_id:
            return AgentResponse(
                response="please provide the order ID you want to cancel.",
                action_taken=None,
                success=True,
                extracted={},
                missing_fields=["order_id"],
                logs=logs + ["missing_field=order_id"],
            )
        
        state.pending_intent = "cancel_order"
        state.order_id = routed.order_id
        state.awaiting_confirmation = True

        state_after = state.to_dict()

        logger.info(f"AGENT | intent=cancel_order | state=awaiting_confirmation")

        return AgentResponse(
            response=f"You are asking to cancel order {routed.order_id}. Reply 'yes' to confirm.",
            action_taken=None,
            success=True,
            response=f"You're about to cancel order {routed.order_id}. Reply 'yes' to confirm.",
            success=True,
            intent="cancel_order",
            workflow_state="awaiting_confirmation",
            state_before=state_before,
            state_after=state_after,
            action_result="pending_confirmation",
            extracted={"order_id": routed.order_id},
            logs=logs + ["state_updated=awaiting_cancel_confirmation"],
        )
    
    if routed.intent == "request_refund":
        missing_fields = []
        if not routed.order_id:
            missing_fields.append("order_id")
        if not routed.reason:
            missing_fields.append("reason")
        
        if missing_fields:
            state.pending_intent = "request_refund"
            state.order_id = routed.order_id
            state.reason = routed.reason

            return AgentResponse(
                response="I need you order id and a refund reason." if len(missing_fields) == 2 else f"Please provide the missing field: { missing_fields[0]}.",
                action_taken=None,
                success=False,
                extracted={
                    "order_id": routed.order_id,
                    "reason": routed.reason,
                },
                missing_fields=missing_fields,
                logs=logs+[f"missing_fields={missing_fields}"],
            )
        
        result = request_refund(routed.order_id, routed.reason, db)
        return AgentResponse(
            response=result["message"],
            action_taken="request_refund",
            success=result["success"],
            extracted={
                "order_id": routed.order_id,
                "reason": routed.reason,
            },
            logs=logs + [f"tool_result={result}"],
        )
    
            logs=logs,
        )

    # fallback
    state_after = state.to_dict()

    logger.info("AGENT | fallback triggered")

    return AgentResponse(
        response="Something went wrong in routing.",
        action_taken=None,
        success=False,
        response="Something went wrong.",
        success=False,
        workflow_state="unable_to_route",
        state_before=state_before,
        state_after=state_after,
        action_result="not_attempted",
        extracted={},
        logs=logs,
    )
