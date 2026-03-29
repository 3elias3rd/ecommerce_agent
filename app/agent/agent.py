from sqlalchemy.orm import Session

from app.agent.router import route_message
from app.agent.schemas import AgentResponse
from app.agent.state import clear_state, get_or_create_state
from app.tools.orders import cancel_order, get_order, request_refund


def handle_agent_message(user_id: str, message: str, db: Session) -> AgentResponse:
    logs: list[str] = []
    state = get_or_create_state(user_id)

    text = message.strip()
    lowered = text.lower()

    logs.append(f"received_message={text}")

    if state.awaiting_confirmation:
        logs.append("state-awaiting_confirmation")

        if lowered in {"yes", "confirm", "please do", "go ahead"}:
            if state.pending_intent == "cancel_order" and state.order_id:
                pending_order_id = state.order_id
                result = cancel_order(pending_order_id, db)
                clear_state (user_id)

                return AgentResponse(
                    response=result["message"],
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
            return AgentResponse(
                response="Okay, I did not take any action.",
                action_taken=None,
                success=True,
                extracted={},
                logs=logs + ["confirmation_declined=true"]
            )
        return AgentResponse(
            response="Please reply with 'yes' to confirm or 'no' to cancel.",
            action_taken=None,
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
        return AgentResponse(
            response="I can help with order lookup, cancellation, or refund requests. Please include an order ID.",
            action_taken=None,
            success=False,
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
        return AgentResponse(
            response=(
                f"Order{order ['order_id']} is currently {order['status']}. "
                f"item: {order['item_name']}. Amount: ${order['amount']}"
            ),
            action_taken="get_order",
            success=True,
            extracted={"order_id": routed.order_id},
            logs=logs + [f"tool_result={result}"],
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

        return AgentResponse(
            response=f"You are asking to cancel order {routed.order_id}. Reply 'yes' to confirm.",
            action_taken=None,
            success=True,
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
    
    return AgentResponse(
        response="Something went wrong in routing.",
        action_taken=None,
        success=False,
        extracted={},
        logs=logs + ["routing_fell_through=true"],
    )
