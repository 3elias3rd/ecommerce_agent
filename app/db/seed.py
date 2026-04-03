from app.db.database import SessionLocal
from app.db.models import Order, RefundRequest


def seed():
    db = SessionLocal()
    try:
        # Clear existing data
        db.query(RefundRequest).delete()
        db.query(Order).delete()

        orders = [
            # ── user_1 ──────────────────────────────────────────────
            # pending  → can cancel, refund blocked (not delivered)
            Order(id="ORD-2001", user_id="user_1", status="pending",   amount=25.99,  item_name="Phone Case"),
            # shipped  → cancel blocked (guardrail), refund blocked
            Order(id="ORD-2002", user_id="user_1", status="shipped",   amount=199.99, item_name="Headphones"),
            # delivered → refund success
            Order(id="ORD-2005", user_id="user_1", status="delivered", amount=89.00,  item_name="Laptop Stand"),

            # ── user_2 ──────────────────────────────────────────────
            # delivered → refund success
            Order(id="ORD-2003", user_id="user_2", status="delivered", amount=75.50,  item_name="Keyboard"),
            # pending  → can cancel
            Order(id="ORD-2006", user_id="user_2", status="pending",   amount=129.99, item_name="Webcam"),
            # shipped  → cancel blocked (guardrail)
            Order(id="ORD-2007", user_id="user_2", status="shipped",   amount=45.00,  item_name="USB Hub"),

            # ── user_3 ──────────────────────────────────────────────
            # cancelled → cancel blocked, refund blocked
            Order(id="ORD-2004", user_id="user_3", status="cancelled", amount=15.00,  item_name="Mouse Pad"),
            # pending  → can cancel
            Order(id="ORD-2008", user_id="user_3", status="pending",   amount=39.99,  item_name="Desk Lamp"),
            # delivered → refund success
            Order(id="ORD-2009", user_id="user_3", status="delivered", amount=349.00, item_name="Monitor"),

            # ── user_4 ──────────────────────────────────────────────
            # pending  → can cancel
            Order(id="ORD-2010", user_id="user_4", status="pending",   amount=159.00, item_name="Mechanical Keyboard"),
            # refunded → cancel blocked, duplicate refund blocked
            Order(id="ORD-2011", user_id="user_4", status="refunded",  amount=19.99,  item_name="Cable Organizer"),
            # delivered → refund success
            Order(id="ORD-2013", user_id="user_4", status="delivered", amount=220.00, item_name="Standing Desk Mat"),

            # ── user_5 ──────────────────────────────────────────────
            # pending  → can cancel
            Order(id="ORD-2012", user_id="user_5", status="pending",   amount=34.99,  item_name="Laptop Sleeve"),
            # delivered → refund success
            Order(id="ORD-2014", user_id="user_5", status="delivered", amount=499.00, item_name="Standing Desk"),
            # shipped  → cancel blocked (guardrail)
            Order(id="ORD-2015", user_id="user_5", status="shipped",   amount=59.99,  item_name="Monitor Arm"),
        ]

        db.add_all(orders)
        db.flush()  # ensure orders are written before refund FK references them

        # ORD-2011 is refunded — needs a matching RefundRequest row
        refunds = [
            RefundRequest(
                order_id="ORD-2011",
                reason="Item arrived damaged",
                status="approved",
            ),
        ]

        db.add_all(refunds)
        db.commit()
        print("✅ Seed complete — 15 orders, 1 refund request")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()