import re
from app.agent.schemas import RoutedIntent
from app.utils.logger import get_logger

logger = get_logger(__name__)

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


def route_message(message: str) -> tuple[RoutedIntent, str] | RoutedIntent:
    text     = message.strip()
    lowered  = text.lower()
    order_id = extract_order_id(text)

    # ── Order status / lookup ──
    if any(phrase in lowered for phrase in [
        "where is my order", "track my order",
        "order status", "where's my order",
        "check order", "check my order",
        "look up", "lookup",
    ]):
        result = RoutedIntent(intent="get_order", order_id=order_id)

    # ── Cancellation ──
    elif "cancel" in lowered:
        result = RoutedIntent(
            intent="cancel_order",
            order_id=order_id,
            need_confirmation=True,
        )

    # ── Refund ──
    elif "refund" in lowered:
        result = RoutedIntent(
            intent="request_refund",
            order_id=order_id,
            reason=extract_reason(text),
        )

    # ── Bare order ID ──
    elif order_id:
        result = RoutedIntent(intent="get_order", order_id=order_id)

    # ── Unknown — escalate to LLM ──
    else:
        # Imported here to avoid circular imports and to prevent the
        # OpenAI client from initialising on every module load
        from app.utils.llm_router import llm_route_message

        logger.info(
            f"ROUTER | source=rule | rule_based=no_match"
            f" | input={text[:60]!r} | escalating=llm"
        )
        return llm_route_message(text)

    logger.info(
        f"ROUTER | source=rule"
        f" | input={text[:60]!r}"
        f" | intent={result.intent}"
        f" | order_id={result.order_id}"
    )
    return result