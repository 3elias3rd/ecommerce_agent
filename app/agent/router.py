import re
from app.agent.schemas import RoutedIntent


ORDER_ID_PATTERN = r"\bORD-\d{4,}\b"


def extract_order_id(message: str) -> str | None:
    match = re.search(ORDER_ID_PATTERN, message.upper())
    return match.group(0) if match else None


def extract_reason(text: str) -> str | None:
    """Extract a refund reason from free-form text."""
    lowered = text.lower()

    if "because" in lowered:
        return text.lower().split("because", 1)[1].strip() or None

    order_id = extract_order_id(text)
    if "for" in lowered and order_id:
        after_order = text.split(order_id, 1)
        if len(after_order) > 1:
            possible_reason = after_order[1].strip(" .:-")
            return possible_reason or None

    return None


def route_message(message: str) -> RoutedIntent:
    text = message.strip()
    lowered = text.lower()
    order_id = extract_order_id(text)

    # ── Order status / lookup ──
    if any(phrase in lowered for phrase in [
        "where is my order", "track my order",
        "order status", "where's my order",
        "check order", "check my order",
        "look up", "lookup",
    ]):
        return RoutedIntent(intent="get_order", order_id=order_id)

    # ── Cancellation ──
    if "cancel" in lowered:
        return RoutedIntent(
            intent="cancel_order",
            order_id=order_id,
            need_confirmation=True,
        )

    # ── Refund ──
    if "refund" in lowered:
        reason = extract_reason(text)
        return RoutedIntent(
            intent="request_refund",
            order_id=order_id,
            reason=reason,
        )

    # ── Bare order ID (e.g. user types "ORD-1002") ──
    if order_id:
        return RoutedIntent(intent="get_order", order_id=order_id)

    return RoutedIntent(intent="unknown")