from sqlalchemy.orm import Session
from app.services.order_service import OrderService
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    order = service.get_order_summary(order_id)

    if not order:
        result = {"success": False, "message": "Order not found."}
    else:
        result = {"success": True, "order": order}

    logger.info(f"TOOL | action=get_order | order_id={order_id} | success={result['success']}")
    return result


def cancel_order(order_id: str, db: Session) -> dict:
    service = OrderService(db)
    result = service.cancel_order(order_id)

    logger.info(f"TOOL | action=cancel_order | order_id={order_id} | success={result['success']}")
    return result


def request_refund(order_id: str, reason: str, db: Session) -> dict:
    service = OrderService(db)
    result = service.request_refund(order_id, reason)

    logger.info(f"TOOL | action=request_refund | order_id={order_id} | success={result['success']}")
    return result