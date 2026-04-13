from sqlalchemy.orm import Session
import time
from contextlib import contextmanager

from app.agent.router import extract_order_id, extract_reason, route_message
from app.agent.schemas import AgentResponse, RoutedIntent
from app.agent.state import clear_state, get_or_create_state, save_state
from app.tools.orders import cancel_order, get_order, request_refund
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────────────
# Timing
# ──────────────────────────────────────────────────────

class RequestTimer:
    """
    Lightweight per-request timer. Records split times for each
    named phase. Only logs if ENABLE_TIMING=true in config.
    """
    # All phases in order — missing ones reported as 0.0ms
    PHASES = ["state_load", "routing", "tool", "state_save"]

    def __init__(self):
        self._start = time.perf_counter()
        self._splits: dict[str, float] = {}
        self._last = self._start

    def split(self, label: str) -> None:
        """Record elapsed time since the last split (or start)."""
        now = time.perf_counter()
        self._splits[label] = round((now - self._last) * 1000, 2)
        self._last = now

    def total_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)

    def log(self, user_id: str, routing_source: str) -> None:
        if not settings.enable_timing:
            return
        parts = " | ".join(
            f"{phase}={self._splits.get(phase, 0.0)}ms"
            for phase in self.PHASES
        )
        logger.info(
            f"TIMING | user_id={user_id} | source={routing_source}"
            f" | {parts} | total={self.total_ms()}ms"
        )


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────

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


def _missing_fields_response(
    intent: str,
    missing_fields: list[str],
    state_before: dict,
    state_after: dict,
    extracted: dict,
    logs: list[str],
) -> AgentResponse:
    """Shared response builder for any slot-filling prompt."""
    response = (
        "To request a refund, I need your order ID and the reason for the refund."
        if len(missing_fields) == 2
        else f"I just need one more thing: {missing_fields[0]}."
    )
    return AgentResponse(
        response=response,
        success=False,
        action_taken=None,
        intent=intent,
        workflow_state="awaiting_missing_fields",
        state_before=state_before,
        state_after=state_after,
        action_attempted=intent,
        action_result="awaiting_input",
        guardrail_triggered=None,
        extracted=extracted,
        missing_fields=missing_fields,
        logs=logs,
    )


def _execute_refund(
    user_id: str,
    order_id: str,
    reason: str,
    state,
    state_before: dict,
    logs: list[str],
    db: Session,
    timer: "RequestTimer | None" = None,
) -> AgentResponse:
    """
    Execute a refund tool call and return the AgentResponse.
    Shared by both the slot-filling path and the fresh-routing path
    to avoid duplicating this logic.
    """
    result = request_refund(order_id, reason, db)
    if timer:
        timer.split("tool")

    guardrail = map_guardrail(result["message"])
    clear_state(user_id)
    if timer:
        timer.split("state_save")

    state_after = state.to_dict()

    if result["success"]:
        logger.info(
            f"AGENT | user_id={user_id} | intent=request_refund | state=action_completed"
            f" | action=request_refund | result=completed | order_id={order_id}"
        )
    else:
        logger.warning(
            f"AGENT | user_id={user_id} | intent=request_refund | state=action_blocked"
            f" | action=request_refund | result=blocked | guardrail={guardrail} | order_id={order_id}"
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
        extracted={"order_id": order_id, "reason": reason},
        logs=logs + [
            "tool_called=request_refund",
            f"tool_success={str(result['success']).lower()}",
        ],
    )


# ──────────────────────────────────────────────────────
# Main entry point
# ──────────────────────────────────────────────────────

def handle_agent_message(user_id: str, message: str, db: Session) -> AgentResponse:
    """
    Public entry point. Owns the request timer — measures total time
    and each phase, logs a TIMING line if ENABLE_TIMING=true.
    """
    timer = RequestTimer()
    response = _handle_agent_message_inner(user_id, message, db, timer)
    timer.log(user_id, routing_source=response.response or "unknown")
    return response


def _handle_agent_message_inner(
    user_id: str, message: str, db: Session, timer: RequestTimer
) -> AgentResponse:
    logs: list[str] = []

    state = get_or_create_state(user_id)
    timer.split("state_load")

    state_before = state.to_dict()
    text = message.strip()
    lowered = text.lower()

    log_kv(logs, "message_received", text)

    # ──────────────────────────────────────────
    # 1) Awaiting confirmation
    # ──────────────────────────────────────────
    if state.awaiting_confirmation:
        log_kv(logs, "workflow_state", "awaiting_confirmation")
        pending_order_id = state.order_id

        if lowered in {"yes", "confirm", "please do", "go ahead"}:
            if state.pending_intent == "cancel_order" and pending_order_id:
                timer.split("routing")  # no routing happened — still record the split
                result = cancel_order(pending_order_id, db)
                timer.split("tool")

                guardrail = map_guardrail(result["message"])
                clear_state(user_id)
                timer.split("state_save")
                state_after = state.to_dict()

                if result["success"]:
                    logger.info(
                        f"AGENT | user_id={user_id} | intent=cancel_order | state=action_completed"
                        f" | action=cancel_order | result=completed | order_id={pending_order_id}"
                    )
                else:
                    logger.warning(
                        f"AGENT | user_id={user_id} | intent=cancel_order | state=action_blocked"
                        f" | action=cancel_order | result=blocked | guardrail={guardrail} | order_id={pending_order_id}"
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

            logger.warning(
                f"AGENT | user_id={user_id} | intent=unknown | state=confirmation_invalid"
                f" | action=None | guardrail=None | order_id={pending_order_id}"
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
                f"AGENT | user_id={user_id} | intent=cancel_order | state=confirmation_declined"
                f" | action=cancel_order | result=declined | order_id={pending_order_id}"
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
            f"AGENT | user_id={user_id} | intent={state.pending_intent} | state=awaiting_confirmation"
            f" | action=None | order_id={pending_order_id}"
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
            state.last_mentioned_order_id = extracted_order_id
            log_kv(logs, "state_order_id_filled", extracted_order_id)

        if extracted_reason and not state.reason:
            state.reason = extracted_reason
            log_kv(logs, "state_reason_filled", True)

        # If the agent already has the order_id and is only waiting for a reason,
        # treat the entire message as the reason — the user is just stating it
        # directly without any signal words (e.g. "wrong item sent")
        if not state.reason and state.order_id and not extracted_order_id:
            state.reason = text
            log_kv(logs, "state_reason_filled_raw", True)

        # Persist any slot updates to Redis
        save_state(state)

        missing_fields: list[str] = []
        if not state.order_id:
            missing_fields.append("order_id")
        if not state.reason:
            missing_fields.append("reason")

        if missing_fields:
            state_after = state.to_dict()
            log_kv(logs, "missing_fields", ",".join(missing_fields))

            logger.info(
                f"AGENT | user_id={user_id} | intent=request_refund | state=awaiting_missing_fields"
                f" | missing={','.join(missing_fields)} | order_id={state.order_id}"
            )

            return _missing_fields_response(
                intent="request_refund",
                missing_fields=missing_fields,
                state_before=state_before,
                state_after=state_after,
                extracted={"order_id": state.order_id, "reason": state.reason},
                logs=logs,
            )

        # All slots filled — execute refund
        return _execute_refund(
            user_id=user_id,
            order_id=state.order_id,
            reason=state.reason,
            state=state,
            state_before=state_before,
            logs=logs,
            db=db,
            timer=timer,
        )

    # ──────────────────────────────────────────
    # 2b) Pending cancel — slot filling
    # ──────────────────────────────────────────
    if state.pending_intent == "cancel_order" and not state.awaiting_confirmation:
        log_kv(logs, "workflow_state", "pending_cancel_slot_fill")

        extracted_order_id = extract_order_id(text)

        if extracted_order_id:
            state.order_id = extracted_order_id
            state.last_mentioned_order_id = extracted_order_id
            state.awaiting_confirmation = True
            save_state(state)
            state_after = state.to_dict()

            logger.info(
                f"AGENT | user_id={user_id} | intent=cancel_order | state=awaiting_confirmation"
                f" | order_id={extracted_order_id} | source=slot_fill"
            )

            return AgentResponse(
                response=(
                    f"You're about to cancel order {extracted_order_id}.\n\n"
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
                extracted={"order_id": extracted_order_id},
                logs=logs + ["state_updated=awaiting_cancel_confirmation"],
            )

        # Still no order ID
        state_after = state.to_dict()

        logger.info(
            f"AGENT | user_id={user_id} | intent=cancel_order | state=awaiting_missing_fields | missing=order_id"
        )

        return AgentResponse(
            response="I still need the order ID to proceed. Please provide it (e.g. ORD-2001).",
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
            logs=logs + ["missing_fields=order_id", "slot_fill_attempt=no_id_found"],
        )

    # ──────────────────────────────────────────
    # 3) Fresh routing
    # ──────────────────────────────────────────
    route_result = route_message(text, user_id=user_id)
    routed, routing_source = normalize_route_result(route_result)
    timer.split("routing")

    log_kv(logs, "routing_source", routing_source)
    log_kv(logs, "intent", routed.intent)
    log_kv(logs, "order_id", routed.order_id)
    log_kv(logs, "reason_present", str(routed.reason is not None).lower())

    # ── Unknown intent ──
    if routed.intent == "unknown":
        state_after = state.to_dict()

        logger.info(
            f"AGENT | user_id={user_id} | intent=unknown | state=unable_to_route"
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

            logger.info(
                f"AGENT | user_id={user_id} | intent=get_order | state=awaiting_missing_fields | missing=order_id"
            )

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
        timer.split("tool")

        # get_order doesn't mutate state — record a near-zero split for consistency
        timer.split("state_save")
        state_after = state.to_dict()

        if not result["success"]:
            guardrail = map_guardrail(result["message"])

            logger.warning(
                f"AGENT | user_id={user_id} | intent=get_order | state=action_blocked"
                f" | guardrail={guardrail} | order_id={routed.order_id}"
            )

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

        # Update conversational context
        state.last_mentioned_order_id = routed.order_id
        save_state(state)

        logger.info(
            f"AGENT | user_id={user_id} | intent=get_order | state=lookup_completed"
            f" | order_id={routed.order_id} | status={order['status']}"
        )

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
        # Use last mentioned order ID if none in this message
        resolved_order_id = routed.order_id or state.last_mentioned_order_id

        if not resolved_order_id:
            state.pending_intent = "cancel_order"
            save_state(state)
            state_after = state.to_dict()

            logger.info(
                f"AGENT | user_id={user_id} | intent=cancel_order | state=awaiting_missing_fields | missing=order_id"
            )

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
        state.order_id = resolved_order_id
        state.awaiting_confirmation = True
        state.last_mentioned_order_id = resolved_order_id
        save_state(state)
        state_after = state.to_dict()

        # Tell the user which order we resolved to if they didn't say it explicitly
        if not routed.order_id:
            log_kv(logs, "order_id_source", "last_mentioned")

        logger.info(
            f"AGENT | user_id={user_id} | intent=cancel_order | state=awaiting_confirmation"
            f" | order_id={resolved_order_id} | order_id_source={'message' if routed.order_id else 'last_mentioned'}"
        )

        return AgentResponse(
            response=(
                f"You're about to cancel order {resolved_order_id}.\n\n"
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
            extracted={"order_id": resolved_order_id},
            logs=logs + ["state_updated=awaiting_cancel_confirmation"],
        )

    # ── Request refund ──
    if routed.intent == "request_refund":
        # Use last mentioned order ID if none in this message
        resolved_order_id = routed.order_id or state.last_mentioned_order_id

        state.pending_intent = "request_refund"
        state.order_id = resolved_order_id
        state.reason = routed.reason
        if resolved_order_id:
            state.last_mentioned_order_id = resolved_order_id
        save_state(state)

        missing_fields: list[str] = []
        if not state.order_id:
            missing_fields.append("order_id")
        if not state.reason:
            missing_fields.append("reason")

        if missing_fields:
            state_after = state.to_dict()
            log_kv(logs, "missing_fields", ",".join(missing_fields))
            if routed.order_id is None and state.last_mentioned_order_id:
                log_kv(logs, "order_id_source", "last_mentioned")

            logger.info(
                f"AGENT | user_id={user_id} | intent=request_refund | state=awaiting_missing_fields"
                f" | missing={','.join(missing_fields)} | order_id={state.order_id}"
            )

            return _missing_fields_response(
                intent="request_refund",
                missing_fields=missing_fields,
                state_before=state_before,
                state_after=state_after,
                extracted={"order_id": state.order_id, "reason": state.reason},
                logs=logs,
            )

        # All slots filled — execute immediately
        return _execute_refund(
            user_id=user_id,
            order_id=state.order_id,
            reason=state.reason,
            state=state,
            state_before=state_before,
            logs=logs,
            db=db,
            timer=timer,
        )

    # ── Fallback ──
    state_after = state.to_dict()

    logger.warning(
        f"AGENT | user_id={user_id} | state=routing_fell_through"
    )

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