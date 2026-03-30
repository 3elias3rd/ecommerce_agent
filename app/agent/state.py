from dataclasses import dataclass
from typing import Optional


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

    def reset(self) -> None:
        self.pending_intent = None
        self.order_id = None
        self.reason = None
        self.awaiting_confirmation = False
        self.last_action = None


conversation_store: dict[str, WorkflowState] = {}


def get_or_create_state(user_id: str) -> WorkflowState:
    if user_id not in conversation_store:
        conversation_store[user_id] = WorkflowState(user_id=user_id)
    return conversation_store[user_id]


def clear_state(user_id: str) -> None:
    if user_id in conversation_store:
        conversation_store[user_id].reset()