from app.db.database import Base, SessionLocal, engine
from app.db.models import Order, OrderStatus

def seed_data():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.query(Order).first()
        if existing:
            print("Seed skipped: Data already exists.")
            return

        orders = [
            Order(
                id="ORD-1001",
                user_id="user_1",
                status=OrderStatus.PENDING.value,
                amount=49.99,
                item_name="Wireless Mouse",
            ),
            Order(
                id="ORD-1002",
                user_id="user_1",
                status=OrderStatus.SHIPPED.value,
                amount=129.99,
                item_name="Mechanical_keyboard",
            ),
            Order(
                id="ORD-1003",
                user_id="user_2",
                status=OrderStatus.DELIVERED.value,
                amount=89.50,
                item_name="USB-C Dock",
            ),
            Order(
                id="ORD-1004",
                user_id="user_3",
                status=OrderStatus.CANCELLED.value,
                amount=19.99,
                item_name="Laptop Sleeve",
            ),
        ]

        db.add_all(orders)
        db.commit()
        print("Seed completed.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()