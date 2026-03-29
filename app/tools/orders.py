from sqlalchemy.orm import Session
from app.services.order_service import OrderService


def get_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    order = service.get_order_summary(order_id)

    if not order:
        return{"success": False, "message": "Order not found."}
    
    return {"success": True, "order": order}

def cancel_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    return service.cancel_order(order_id)

def request_refund(order_id: str, reason: str, db: Session) -> dict:
    service = OrderService(db)
    return service.request_refund(order_id, reason)


    