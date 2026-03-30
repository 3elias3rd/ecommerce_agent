from typing import Literal, Optional
from pydantic import BaseModel, Field


IntentType = Literal["get_order", "cancel_order", "request_refund", "unknown"]


class AgentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class RoutedIntent(BaseModel):
    intent: IntentType
    order_id: Optional[str] = None
    reason: Optional[str] = None
    needs_confirmation: bool = False  # FIXED NAME


class AgentResponse(BaseModel):
    response: str
    success: bool

    action_taken: Optional[str] = None
    extracted: dict = Field(default_factory=dict)  # FIXED

    logs: list[str] = Field(default_factory=list)  # FIXED
    missing_fields: list[str] = Field(default_factory=list)  # FIXED

    intent: Optional[str] = None
    workflow_state: Optional[str] = None

    state_before: dict = Field(default_factory=dict)  # FIXED
    state_after: dict = Field(default_factory=dict)   # FIXED

    action_attempted: Optional[str] = None
    action_result: Optional[str] = None
    guardrail_triggered: Optional[str] = None