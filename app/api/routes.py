from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.order_service import OrderService

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok"}


@router.get("/orders/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    service = OrderService(db)
    order = service.get_order_summary(order_id=order_id)

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    return order