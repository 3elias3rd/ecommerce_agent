from sqlalchemy.orm import Session
from app.services.order_service import OrderService


def get_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    order = service.get_order_summary(order_id)

    if not order:
        return {"success": False, "message": "Order not found."}

    return {"success": True, "order": order}


def cancel_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    result = service.cancel_order(order_id)

    if result.get("success"):
        order = result.get("order")

        if not order:
            order = service.get_order_summary(order_id)

        return {
            "success": True,
            "message": result["message"],
            "order": order,
        }

    return {
        "success": False,
        "message": result["message"],
    }


def request_refund(order_id: str, reason: str, db: Session) -> dict:
    service = OrderService(db)
    result = service.request_refund(order_id, reason)

    if result.get("success"):
        return {
            "success": True,
            "message": result["message"],
            "refund": result.get("refund"),
        }

    return {
        "success": False,
        "message": result["message"],
    }