from typing import Literal, Optional
from pydantic import BaseModel, Field


Intent_type = Literal["get_order", "cancel_order", "request_refund", "unknown"]

class AgentRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class RoutedIntent(BaseModel):
    intent: Intent_type
    order_id: Optional[str] = None
    reason: Optional[str] = None
    need_confirmation: bool = False


class AgentResponse(BaseModel):
    response: str
    action_taken: str | None = None
    success: bool
    extracted: dict
    missing_fields: list[str] = []
    logs: list[str] = []