import re
from app.agent.schemas import RoutedIntent


ORDER_ID_PATTERN = r"\bORD-\d{4,}\b"


def extract_order_id(message: str) -> str | None:
    match = re.search(ORDER_ID_PATTERN, message.upper())
    return match.group(0) if match else None

def extract_reason(message: str) -> str | None:
    lowered = message.lower()

    if "because" in lowered:
        return message.split("because", 1)[1].strip()

    return None


def route_message(message: str) -> RoutedIntent:
    text = message.strip()
    lowered = text.lower()
    order_id = extract_order_id(text)

    # 1. Direct order lookup (high priority)
    if order_id and not any(word in lowered for word in ["cancel", "refund"]):
        return RoutedIntent(intent="get_order", order_id=order_id)

    # 2. Lookup phrases
    LOOKUP_PHRASES = [
        "where is my order",
        "track my order",
        "order status",
        "where's my order",
        "check my order",
        "check order",
    ]

    if any(phrase in lowered for phrase in LOOKUP_PHRASES):
        return RoutedIntent(intent="get_order", order_id=order_id)

    # 3. Cancel
    if any(word in lowered for word in ["cancel", "stop order"]):
        return RoutedIntent(
            intent="cancel_order",
            order_id=order_id,
            needs_confirmation=True,
        )

    # 4. Refund
    if "refund" in lowered:
        reason = None

        if "because" in lowered:
            reason = text.split("because", 1)[1].strip()
        elif "for" in lowered and order_id:
            after_order = text.split(order_id, 1)
            if len(after_order) > 1:
                possible_reason = after_order[1].strip(" .:-")
                reason = possible_reason or None

        return RoutedIntent(
            intent="request_refund",
            order_id=order_id,
            reason=reason,
        )

    return RoutedIntent(intent="unknown")