class TestHealthAPI:
    def test_health_check(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestOrderAPI:
    def test_get_order_success(self, client):
        response = client.get("/orders/ORD-1001")

        assert response.status_code == 200
        data = response.json()
        assert data["order_id"] == "ORD-1001"

    def test_get_order_not_found(self, client):
        response = client.get("/orders/ORD-9999")

        assert response.status_code == 404


class TestActionAPI:
    def test_cancel_order_success(self, client):
        response = client.post("/orders/ORD-1001/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["order"]["status"] == "cancelled"
    
    def test_cancel_order_blocked(self, client):
        response = client.post("/orders/ORD-1002/cancel")

        assert response.status_code == 400
        assert response.json()["detail"] == "Shipped orders cannot be cancelled."
    
    def test_request_refund_success(self, client):
        response = client.post(
            "/orders/ORD-1003/refund",
            json={"reason": "Item arrived damaged"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["refund"]["order_id"] == "ORD-1003"
    
    def test_request_refund_blocked(self, client):
        response = client.post(
            "/orders/ORD-1001/refund",
            json={"reason": "changed my mind"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Only delivered orders are eligible for refund requests."

class TestAgentApi:
    def test_agent_lookup(self, client):
        response = client.post(
            "/agent/chat",
            json={
                "user_id": "user_1",
                "message": "Where is my order ORD-1002?"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action_taken"] == "get_order"
    

    def test_agent_cancel_confirmation_flow(self, client):
        first = client.post(
            "/agent/chat",
            json={
                "user_id": "user_1",
                "message": "Cancel my order ORD-1001",
            },
        )
        second = client.post(
            "/agent/chat",
            json={
                "user_id": "user_1",
                "message": "yes",
            },
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["action_taken"] == "cancel_order"

    def test_agent_refund_missing_order_id(self, client):
        response = client.post(
            "/agent/chat",
            json={
                "user_id": "user_2",
                "message": "I want a refund because it arrived damaged",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "order_id" in data["missing_fields"]