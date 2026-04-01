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
    # ── Core response ──
    response: str
    success: bool

    # ── Intent & workflow ──
    intent: Optional[str] = None
    workflow_state: Optional[str] = None

    # ── Actions ──
    action_taken: Optional[str] = None
    action_attempted: Optional[str] = None
    action_result: Optional[str] = None

    # ── Guardrails ──
    guardrail_triggered: Optional[str] = None

    # ── State transitions ──
    state_before: Optional[dict] = None
    state_after: Optional[dict] = None

    # ── Extracted entities ──
    extracted: dict = {}
    missing_fields: list[str] = []

    # ── Debug ──
    logs: list[str] = []