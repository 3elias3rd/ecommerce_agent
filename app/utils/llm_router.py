import json
from openai import OpenAI, APIError, APITimeoutError

from app.agent.schemas import RoutedIntent
from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Client (module-level, reused across requests) ──────────────
_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    global _client
    if _client is not None:
        return _client
    if not settings.openai_api_key:
        logger.warning("LLM_ROUTER | openai_api_key not set | llm_routing_disabled")
        return None
    _client = OpenAI(api_key=settings.openai_api_key)
    return _client


# ── System prompt ───────────────────────────────────────────────
_SYSTEM_PROMPT = """
You are an intent extraction system for an order management agent.
Extract the user's intent and any entities from their message.

Valid intents:
- get_order: user wants to check, track, view, or look up an order
- cancel_order: user wants to cancel or stop an order
- request_refund: user wants a refund, their money back, or to return an item
- unknown: message does not relate to any of the above

Rules:
- order_id must match the pattern ORD-XXXX (e.g. ORD-2001) exactly as written in the message. If not present, return null.
- reason must only be extracted for request_refund intent. For all other intents return null.
- reason should capture why the user wants a refund in their own words. If no reason is given, return null.
- Return ONLY valid JSON. No explanation, no markdown, no code fences.

Response format:
{"intent": "get_order|cancel_order|request_refund|unknown", "order_id": "ORD-XXXX or null", "reason": "string or null"}
""".strip()


# ── Main extraction function ────────────────────────────────────

def llm_route_message(text: str) -> tuple[RoutedIntent, str]:
    """
    Use OpenAI to extract intent and entities from a message.
    Returns a tuple of (RoutedIntent, "llm") on success,
    or (RoutedIntent(intent="unknown"), "llm_fallback") on any failure.
    """
    client = _get_client()

    if not client:
        return RoutedIntent(intent="unknown"), "llm_unavailable"

    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=settings.router_temperature,
            timeout=settings.router_timeout,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or ""
        data = json.loads(raw)

        intent    = data.get("intent", "unknown")
        order_id  = data.get("order_id") or None
        reason    = data.get("reason") or None

        # Validate intent is one of the allowed values
        valid_intents = {"get_order", "cancel_order", "request_refund", "unknown"}
        if intent not in valid_intents:
            logger.warning(
                f"LLM_ROUTER | invalid_intent={intent!r} | falling_back=unknown"
            )
            return RoutedIntent(intent="unknown"), "llm_invalid"

        logger.info(
            f"LLM_ROUTER | intent={intent}"
            f" | order_id={order_id}"
            f" | reason_present={reason is not None}"
            f" | model={settings.openai_model}"
        )

        return RoutedIntent(
            intent=intent,
            order_id=order_id,
            reason=reason,
            need_confirmation=(intent == "cancel_order"),
        ), "llm"

    except APITimeoutError:
        logger.warning(
            f"LLM_ROUTER | error=timeout"
            f" | timeout={settings.router_timeout}s"
            f" | falling_back=unknown"
        )
        return RoutedIntent(intent="unknown"), "llm_timeout"

    except APIError as e:
        logger.warning(
            f"LLM_ROUTER | error=api_error"
            f" | detail={e}"
            f" | falling_back=unknown"
        )
        return RoutedIntent(intent="unknown"), "llm_api_error"

    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(
            f"LLM_ROUTER | error=parse_error"
            f" | detail={e}"
            f" | falling_back=unknown"
        )
        return RoutedIntent(intent="unknown"), "llm_parse_error"

    except Exception as e:
        logger.warning(
            f"LLM_ROUTER | error=unexpected"
            f" | detail={e}"
            f" | falling_back=unknown"
        )
        return RoutedIntent(intent="unknown"), "llm_error"