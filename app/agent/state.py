from dataclasses import dataclass, field
from typing import Optional

@dataclass
class WorkflowState:
    user_id: str
    pending_intent: Optional[str] = None
    order_id: Optional[str] = None
    reason: Optional[str] = None
    awaiting_confirmation: bool = False
    last_action: Optional[str] = None


conversation_store: dict[str, WorkflowState] = {}


def get_or_create_state(user_id: str) -> WorkflowState:
    if user_id not in conversation_store:
        conversation_store[user_id] = WorkflowState(user_id=user_id)
    return conversation_store[user_id]

def clear_state(user_id: str) -> None:
    if user_id in conversation_store:
        conversation_store[user_id] = WorkflowState(user_id=user_id)