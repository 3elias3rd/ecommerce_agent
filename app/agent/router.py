import re
from app.agent.schemas import RoutedIntent


ORDER_ID_PATTERN = r"\bORD-\d{4,}\b"


def extract_order_id(message: str) -> str | None:
    match = re.search(ORDER_ID_PATTERN, message.upper())
    return match.group(0) if match else None

def route_message(message: str) -> RoutedIntent:
    text = message.strip()
    lowered = text.lower()
    order_id = extract_order_id(text)

    if any(phrase in lowered for phrase in ["where is my order", "track my order", "order status", "where's my order"]):
        return RoutedIntent(intent="get_order", order_id=order_id)
    
    if "cancel" in lowered:
        return RoutedIntent(
            intent="cancel_order",
            order_id=order_id,
            need_confirmation=True,
        )
    if "refund" in lowered:
        reason = None

        if "because" in lowered:
            reason = text.lower().split("because", 1)[1].strip()
        elif "for" in lowered and order_id:
            # Fallback
            after_order = text.split(order_id, 1)
            if len(after_order) > 1:
                possible_reason = after_order[1].strip(" .:-")
                reason = possible_reason or None
        
        return RoutedIntent(
            intent="request_refund",
            order_id=order_id,
            reason=reason
        )
    return RoutedIntent(intent="unknown")