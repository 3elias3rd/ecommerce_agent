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
        # New — natural lookup phrases
        "where is my package", "where's my package",
        "has it shipped", "has my order shipped",
        "any updates on my order", "any updates on",
        "track my delivery", "track my package",
        "show me my order", "show my order",
        "what happened to my order",
        "is it on the way", "is my order on its way",
        "find my order", "get me the details",
        "order details", "delivery status",
        "what's the status", "what is the status",
        "pull up my order", "pull up order",
        "when will my order", "when will it arrive",
        "expected delivery", "delivery update",
        "has my package", "where is it",
    ]):
        result = RoutedIntent(intent="get_order", order_id=order_id)

    # ── Cancellation ──
    elif any(phrase in lowered for phrase in [
        "cancel",
        # New — natural cancellation phrases
        "changed my mind", "change my mind",
        "don't want it anymore", "dont want it anymore",
        "don't want this anymore", "dont want this anymore",
        "no longer need", "no longer want",
        "stop my order", "stop the order", "stop my purchase",
        "want to stop", "like to stop",
        "reverse my order", "reverse this order", "reverse the order",
        "can i reverse", "reverse this",
        "undo my order", "undo the order", "undo my purchase",
        "back out", "back out of",
        "abort my order", "abort the order", "abort order",
        "drop my order", "drop the order", "drop order",
        "remove my order", "remove the order",
        "i don't want", "i dont want",
        "want to return and cancel",
    ]):
        result = RoutedIntent(
            intent="cancel_order",
            order_id=order_id,
            need_confirmation=True,
        )

    # ── Refund ──
    elif any(phrase in lowered for phrase in [
        "refund", "money back", "return",
        # New — natural refund phrases
        "arrived damaged", "arrived broken",
        "wrong item", "incorrect item", "wrong product",
        "send it back", "send this back", "send back",
        "get my money", "get me my money",
        "charged twice", "double charged", "overcharged",
        "item is broken", "item was broken", "it's broken", "its broken",
        "this is broken", "this was broken",
        "not what i ordered", "not what I ordered",
        "compensation",
        "reimbursement", "reimburse",
        "dispute", "chargeback",
        "defective", "damaged item", "damaged product",
        "never arrived", "never showed up", "didn't arrive",
        "missing item", "item missing",
        "want my money",
    ]):
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