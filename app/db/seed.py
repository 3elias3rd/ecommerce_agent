from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import Order, RefundRequest


def seed(db: Session = None) -> None:
    """
    Wipe and re-seed all test orders.
    Pass an existing db session (e.g. from a FastAPI endpoint) or leave None
    to open and manage a session internally.
    """
    external_db = db is not None
    if not external_db:
        db = SessionLocal()

    try:
        # Clear existing data
        db.query(RefundRequest).delete()
        db.query(Order).delete()

        orders = [
            # ── user_1 ──────────────────────────────────────────────
            Order(id="ORD-2001", user_id="user_1", status="pending",   amount=25.99,  item_name="Phone Case"),
            Order(id="ORD-2002", user_id="user_1", status="shipped",   amount=199.99, item_name="Headphones"),
            Order(id="ORD-2005", user_id="user_1", status="delivered", amount=89.00,  item_name="Laptop Stand"),

            # ── user_2 ──────────────────────────────────────────────
            Order(id="ORD-2003", user_id="user_2", status="delivered", amount=75.50,  item_name="Keyboard"),
            Order(id="ORD-2006", user_id="user_2", status="pending",   amount=129.99, item_name="Webcam"),
            Order(id="ORD-2007", user_id="user_2", status="shipped",   amount=45.00,  item_name="USB Hub"),

            # ── user_3 ──────────────────────────────────────────────
            Order(id="ORD-2004", user_id="user_3", status="cancelled", amount=15.00,  item_name="Mouse Pad"),
            Order(id="ORD-2008", user_id="user_3", status="pending",   amount=39.99,  item_name="Desk Lamp"),
            Order(id="ORD-2009", user_id="user_3", status="delivered", amount=349.00, item_name="Monitor"),

            # ── user_4 ──────────────────────────────────────────────
            Order(id="ORD-2010", user_id="user_4", status="pending",   amount=159.00, item_name="Mechanical Keyboard"),
            Order(id="ORD-2011", user_id="user_4", status="refunded",  amount=19.99,  item_name="Cable Organizer"),
            Order(id="ORD-2013", user_id="user_4", status="delivered", amount=220.00, item_name="Standing Desk Mat"),

            # ── user_5 ──────────────────────────────────────────────
            Order(id="ORD-2012", user_id="user_5", status="pending",   amount=34.99,  item_name="Laptop Sleeve"),
            Order(id="ORD-2014", user_id="user_5", status="delivered", amount=499.00, item_name="Standing Desk"),
            Order(id="ORD-2015", user_id="user_5", status="shipped",   amount=59.99,  item_name="Monitor Arm"),
        ]

        db.add_all(orders)
        db.flush()

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
        if not external_db:
            db.close()


def reset_db(db: Session) -> dict:
    """
    Wipe and re-seed all orders, and clear all Redis workflow state.
    Called by the admin reset endpoint — safe to call at any time.
    """
    # Re-seed the database
    seed(db)

    # Clear all Redis state so no user is left mid-flow after a reset
    try:
        from app.agent.state import _redis, _memory_store
        if _redis:
            # Delete all agent state keys
            keys = _redis.keys("agent:state:*")
            if keys:
                _redis.delete(*keys)
        # Always clear memory store too
        _memory_store.clear()
        state_reset = True
    except Exception:
        state_reset = False

    return {
        "success": True,
        "message": "Database re-seeded and all session state cleared.",
        "orders_seeded": 15,
        "session_state_cleared": state_reset,
    }


if __name__ == "__main__":
    seed()