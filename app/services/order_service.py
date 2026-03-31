from sqlalchemy.orm import Session

from app.db.models import Order, OrderStatus, RefundRequest, RefundStatus
from app.tools.validators import validate_cancel_order, validate_refund_request
from app.utils.logger import get_logger

logger = get_logger(__name__)


class OrderService:
    def __init__(self, db: Session):
        self.db = db

    def get_order_by_id(self, order_id: str) -> Order | None:
        return self.db.query(Order).filter(Order.id == order_id).first()
    
    def get_orders_for_user(self, user_id: str) -> list[Order]:
        return self.db.query(Order).filter(Order.user_id == user_id).all()
    
    def get_order_summary(self, order_id: str) -> dict | None:
        order = self.get_order_by_id(order_id)
        if not order:
            return None
        
        return{
            "order_id": order.id,
            "user_id": order.user_id,
            "status": order.status,
            "amount": order.amount,
            "item_name": order.item_name,
            "created_at": order.created_at.isoformat(),
        }
    
    def cancel_order(self, order_id: str) -> dict:
        logger.info(f"cancel_order called | order_id={order_id}")

        order = self.get_order_by_id(order_id)
        if not order:
            logger.warning(f"cancel_order failed | order_id={order_id} | reason=not_found")
            return {"success": False, "message": "Order not found."}
        
        valid, message = validate_cancel_order(order)
        if not valid:
            logger.warning(f"cancel_order blocked | order_id={order_id} | reason={message}")
            return {"success": False, "message": message}
        
        order.status = OrderStatus.CANCELLED.value
        self.db.commit()
        self.db.refresh(order)

        logger.info(f"cancel_order success | order_id={order_id} | new_status={order.status}")
        return {
            "success": True,
            "message": "Order cancelled successfully.",
            "order": self.get_order_summary(order_id),
        }
    
    def request_refund(self, order_id: str, reason: str) -> dict:
        logger.info(f"request_refund called | order_id={order_id}")

        order = self.get_order_by_id(order_id)
        if not order:
            logger.warning(f"request_refund failed | order_id={order_id} | reason=notfound")
            return {"success": False, "message": "Order not found."}

        existing_refund = (
            self.db.query(RefundRequest)
            .filter(RefundRequest.order_id == order_id)
            .first()
        )

        valid, message = validate_refund_request(
            order=order,
            reason=reason,
            has_existing_refund=existing_refund is not None,
        )

        if not valid:
            logger.warning(f"request_refund blocked | order_id{order_id} |reason={message}")
            return {"success": False, "message": message}
        
        refund = RefundRequest(
            order_id=order_id,
            reason=reason.strip(),
            status=RefundStatus.REQUESTED.value,
        )

        self.db.add(refund)
        self.db.commit()
        self.db.refresh(refund)

        return {
            "success": True,
            "message": "Refund request submitted successfully.",
            "refund": {
                "refund_id": refund.id,
                "order_id": refund.order_id,
                "status": refund.status,
                "created_at": refund.created_at.isoformat(),
                "reason": refund.status,
            },
        }
    