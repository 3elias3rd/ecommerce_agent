import json
from dataclasses import dataclass, asdict
from typing import Optional

import redis

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Redis client (module-level, connection pooled) ──
try:
    _redis = redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
    _redis.ping()
    logger.info(f"STATE | backend=redis | url={settings.redis_url}")
except Exception as e:
    logger.warning(f"STATE | backend=memory | redis_unavailable | reason={e}")
    _redis = None

# ── In-memory fallback ──
_memory_store: dict[str, "WorkflowState"] = {}


def _redis_key(user_id: str) -> str:
    return f"agent:state:{user_id}"


# ──────────────────────────────────────────────────────
# WorkflowState
# ──────────────────────────────────────────────────────

@dataclass
class WorkflowState:
    user_id: str
    pending_intent: Optional[str] = None
    order_id: Optional[str] = None
    reason: Optional[str] = None
    awaiting_confirmation: bool = False
    last_action: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "pending_intent": self.pending_intent,
            "order_id": self.order_id,
            "reason": self.reason,
            "awaiting_confirmation": self.awaiting_confirmation,
            "last_action": self.last_action,
        }


# ──────────────────────────────────────────────────────
# Serialization helpers
# ──────────────────────────────────────────────────────

def _serialize(state: WorkflowState) -> str:
    return json.dumps(asdict(state))


def _deserialize(user_id: str, raw: str) -> WorkflowState:
    data = json.loads(raw)
    return WorkflowState(
        user_id=data.get("user_id", user_id),
        pending_intent=data.get("pending_intent"),
        order_id=data.get("order_id"),
        reason=data.get("reason"),
        awaiting_confirmation=data.get("awaiting_confirmation", False),
        last_action=data.get("last_action"),
    )


# ──────────────────────────────────────────────────────
# Redis operations (with fallback on any exception)
# ──────────────────────────────────────────────────────

def _redis_get(user_id: str) -> Optional[WorkflowState]:
    try:
        raw = _redis.get(_redis_key(user_id))
        if raw:
            return _deserialize(user_id, raw)
        return None
    except Exception as e:
        logger.warning(f"STATE | redis_get_failed | user_id={user_id} | reason={e} | falling_back=memory")
        return None


def _redis_set(state: WorkflowState) -> bool:
    try:
        _redis.setex(_redis_key(state.user_id), settings.state_ttl, _serialize(state))
        return True
    except Exception as e:
        logger.warning(f"STATE | redis_set_failed | user_id={state.user_id} | reason={e} | falling_back=memory")
        return False


def _redis_delete(user_id: str) -> bool:
    try:
        _redis.delete(_redis_key(user_id))
        return True
    except Exception as e:
        logger.warning(f"STATE | redis_delete_failed | user_id={user_id} | reason={e} | falling_back=memory")
        return False


# ─────────────────
# Public interface 
# ─────────────────

def get_or_create_state(user_id: str) -> WorkflowState:
    """Load state from Redis, fall back to memory, create fresh if not found."""
    if _redis:
        state = _redis_get(user_id)
        if state:
            return state
        state = WorkflowState(user_id=user_id)
        if not _redis_set(state):
            _memory_store[user_id] = state
        return state

    # Memory fallback
    if user_id not in _memory_store:
        _memory_store[user_id] = WorkflowState(user_id=user_id)
    return _memory_store[user_id]


def save_state(state: WorkflowState) -> None:
    """
    Persist state after mutations.
    Call this in agent.py after any state field is modified.
    """
    if _redis:
        if not _redis_set(state):
            _memory_store[state.user_id] = state
    else:
        _memory_store[state.user_id] = state


def clear_state(user_id: str) -> None:
    """Reset state for a user (after action completes or is declined)."""
    fresh = WorkflowState(user_id=user_id)

    if _redis:
        if not _redis_delete(user_id):
            _memory_store[user_id] = fresh
        _memory_store.pop(user_id, None)
    else:
        _memory_store[user_id] = fresh