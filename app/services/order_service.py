from sqlalchemy.orm import Session
from app.db.models import Order


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
            "create_at": order.created_at.isoformat(),
        }