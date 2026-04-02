import os
import tempfile

from app.db.models import Order, OrderStatus
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker 

from app.agent.state import clear_state
from app.db.database import Base, get_db
from app.db.models import Order, OrderStatus
from app.main import app


@pytest.fixture
def test_db():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    database_url = f"sqlite:///{db_path}"

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        os.close(db_fd)
        os.unlink(db_path)
    

@pytest.fixture
def seeded_db(test_db):
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
            item_name="Mechanical Keyboard",
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

    test_db.add_all(orders)
    test_db.commit()
    return test_db

@pytest.fixture
def client(seeded_db):
    def override_get_db():
        try:
            yield seeded_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    clear_state("user_1")
    clear_state("user_2")
    clear_state("user_3")

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
                