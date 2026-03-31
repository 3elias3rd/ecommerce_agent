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

# app/db/seed_orders.py
from app.db.database import SessionLocal
from app.db.models import Order

def seed():
    db = SessionLocal()

    orders = [
        Order(id="ORD-2001", user_id="user_1", status="pending", amount=25.99, item_name="Phone Case"),
        Order(id="ORD-2002", user_id="user_1", status="shipped", amount=199.99, item_name="Headphones"),
        Order(id="ORD-2003", user_id="user_2", status="delivered", amount=75.50, item_name="Keyboard"),
        Order(id="ORD-2004", user_id="user_3", status="cancelled", amount=15.00, item_name="Mouse Pad"),
    ]

    for order in orders:
        db.merge(order)  # prevents duplicates

    db.commit()
    db.close()


if __name__ == "__main__":
    seed()

