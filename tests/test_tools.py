from app.db.models import OrderStatus, RefundRequest
from app.tools.orders import cancel_order, get_order, request_refund


class TestGetOrderTool:
    def test_get_order_success(self, seeded_db):
        result = get_order("ORD-1001", seeded_db)

        assert result["success"] is True
        assert result["order"]["order_id"] == "ORD-1001"

    def test_get_order_not_found(self, seeded_db):
        result = get_order("ORD-9999", seeded_db)

        assert result["success"] is False
        assert result["message"] == "Order not found."


class TestCancelOrderTool:
    def test_cancel_order_success(self, seeded_db):
        result = cancel_order("ORD-1001", seeded_db)

        assert result["success"] is True
        assert result["order"]["status"] == OrderStatus.CANCELLED.value

    def test_cancel_order_blocked_for_shipping(self, seeded_db):
        result = cancel_order("ORD-1002", seeded_db)

        assert result["success"] is False
        assert result["message"] == "Shipped orders cannot be cancelled."

    def test_cancel_order_blocked_for_already_cancelled(self, seeded_db):
        result = cancel_order("ORD-1004", seeded_db)

        assert result["success"] is False
        assert result["message"] == "Order is already cancelled."

class TestRefundTool:
    def test_request_refund_success(self, seeded_db):
        result = request_refund("ORD-1003", "Item arrived damaged", seeded_db)

        assert result["success"] is True
        assert result["refund"]["order_id"] == "ORD-1003"
        assert result["refund"]["status"] == "requested"
    
    def test_request_refund_require_delivered_order(self, seeded_db):
        result = request_refund("ORD-1001", "Changed my mind", seeded_db)

        assert result["success"] is False
        assert result["message"] == "Refunds can only be requested after an order has been delivered."
        
    
    def test_request_refund_requires_reason(self, seeded_db):
        result = request_refund("ORD-1003", "  ", seeded_db)

        assert result["success"] is False
        assert result["message"] == "Refund reason is required."

    
    def test_request_refund_cannot_be_requested_twice(self, seeded_db):
        first = request_refund("ORD-1003", "Item arrived damaged", seeded_db)
        second = request_refund("ORD-1003", "Still damaged", seeded_db)

        assert first["success"] is True
        assert second["success"] is False

        assert second["message"] == "A refund has already been requested for this order."

        refunds = seeded_db.query(RefundRequest).filter(RefundRequest.order_id == "ORD-1003").all()

        assert len(refunds) == 1