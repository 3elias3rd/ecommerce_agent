import re
from app.agent.schemas import RoutedIntent
from app.utils.logger import get_logger

logger = get_logger(__name__)

ORDER_ID_PATTERN = r"\bORD[\s_-]?\d{4,}\b"


def extract_order_id(message: str) -> str | None:
    """
    Extract and normalise an order ID from free-form text.
    Handles: ORD-2001, ORD_2001, ORD 2001, ORD2001 (case-insensitive).
    Always returns the canonical format: ORD-XXXX.
    """
    match = re.search(ORDER_ID_PATTERN, message, flags=re.IGNORECASE)
    if not match:
        return None
    # Normalise to canonical ORD-XXXX format
    digits = re.search(r"\d{4,}", match.group(0)).group(0)
    return f"ORD-{digits}"


def extract_reason(text: str) -> str | None:
    """
    Extract a refund reason from free-form text.

    Handles all of these naturally:
      - "because it arrived damaged"
      - "it arrived damaged"
      - "the item was broken"
      - "wrong item sent"
      - "ORD-2003 it never arrived"

    Does NOT extract filler phrases like:
      - "I want a refund for ORD-2014"  → no reason
      - "refund ORD-2015"               → no reason
      - "I need a refund"               → no reason
    """
    lowered = text.lower().strip()
    order_id = extract_order_id(text)

    # Words that indicate the message is just a refund request with no reason
    _FILLER_ONLY = {
        "refund", "i want a refund", "i need a refund", "i'd like a refund",
        "i would like a refund", "can i get a refund", "please refund",
        "money back", "return", "i want my money back",
    }

    # Remove the order ID from the text so it doesn't pollute the reason
    clean = text
    if order_id:
        clean = re.sub(re.escape(order_id), "", text, flags=re.IGNORECASE).strip(" ,.-:")
    clean = clean.strip()

    # Strip leading intent phrases — what's left should be the reason
    _INTENT_PREFIXES = [
        "i want a refund for", "i need a refund for", "i'd like a refund for",
        "i would like a refund for", "can i get a refund for",
        "please refund", "refund for", "refund",
    ]
    clean_lower = clean.lower()
    for prefix in _INTENT_PREFIXES:
        if clean_lower.startswith(prefix):
            clean = clean[len(prefix):].strip(" ,.-:")
            clean_lower = clean.lower()
            break

    # Always strip leading causal connectors after intent prefix removal
    for opener in ["because ", "since ", "as "]:
        if clean_lower.startswith(opener):
            clean = clean[len(opener):].strip()
            clean_lower = clean.lower()
            break

    # Reject if nothing meaningful is left
    if not clean or len(clean) <= 2:
        return None

    # Reject if what remains is still just a filler phrase
    if clean.lower() in _FILLER_ONLY:
        return None

    # Reject if it's only the order ID pattern
    if re.fullmatch(ORDER_ID_PATTERN, clean.upper()):
        return None

    return clean


def route_message(message: str, user_id: str = "unknown") -> tuple[RoutedIntent, str] | RoutedIntent:
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
    elif "refund" in lowered or "money back" in lowered or "return" in lowered:
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
        from app.utils.llm_router import llm_route_message
        logger.info(
            f"ROUTER | user_id={user_id} | source=rule | result=no_match | escalating=llm"
            f" | input={text[:60]!r}"
        )
        return llm_route_message(text, user_id=user_id)

    logger.info(
        f"ROUTER | user_id={user_id} | source=rule | intent={result.intent}"
        f" | order_id={result.order_id} | input={text[:60]!r}"
    )
    return result