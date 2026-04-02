from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.agent.agent import handle_agent_message
from app.agent.schemas import AgentRequest
from app.agent.state import clear_state
from app.db.database import get_db
from app.services.order_service import OrderService
from app.tools.orders import cancel_order, request_refund


router = APIRouter()


class RefundRequestBody(BaseModel):
    reason: str


# ── Health ────────────────────────────────────────────
@router.get("/health")
def health_check():
    return {"status": "ok"}


# ── Orders ────────────────────────────────────────────
@router.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    service = OrderService(db)
    order = service.get_order_summary(order_id=order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.post("/orders/{order_id}/cancel")
def cancel_order_route(order_id: str, db: Session = Depends(get_db)):
    result = cancel_order(order_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/orders/{order_id}/refund")
def request_refund_route(
    order_id: str,
    body: RefundRequestBody,
    db: Session = Depends(get_db),
):
    result = request_refund(order_id, body.reason, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# ── Agent ─────────────────────────────────────────────
@router.post("/agent/chat")
def agent_chat(body: AgentRequest, db: Session = Depends(get_db)):
    return handle_agent_message(
        user_id=body.user_id,
        message=body.message,
        db=db,
    )


@router.post("/agent/reset")
def agent_reset(body: AgentRequest, db: Session = Depends(get_db)):
    clear_state(body.user_id)
    return {"success": True, "message": "Session reset."}