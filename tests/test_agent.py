from app.agent.agent import handle_agent_message


class TestAgentLookupFLow:
    def test_lookup_order_success(self, seeded_db):
        result = handle_agent_message(
            user_id="user_1",
            message="Where is my order ORD-1002?",
            db=seeded_db,
        )

        assert result.success is True
        assert result.action_taken == "get_order"
        assert "ORD-1002" in result.response
        assert "shipped" in result.response.lower()

    
class TestAgentCancelFlow:
    def test_cancel_requires_confirmation(self, seeded_db):
        first = handle_agent_message(
            user_id="user_1",
            message="Cancel my order ORD-1001",
            db=seeded_db,
        )

        assert first.success is True
        assert first.action_taken is None
        assert "Reply 'yes' to confirm" in first.response

    def test_cancel_confirmation_executes_action(self, seeded_db):
        first =handle_agent_message(
            user_id="user_1",
            message="Cancel my order ORD-1001",
            db=seeded_db,
        )
        second = handle_agent_message(
            user_id="user_1",
            message="yes",
            db=seeded_db,
        )

        assert first.success is True
        assert second.success is True
        assert second.action_taken == "cancel_order"
        assert "cancelled" in second.response.lower()

    def test_cancel_confirmation_declined(self, seeded_db):
        handle_agent_message(
            user_id="user_1",
            message="Cancel my order ORD-1001",
            db=seeded_db,
        )   
        second = handle_agent_message(
            user_id="user_1",
            message="no",
            db=seeded_db,
        )

        assert second.success is True
        assert second.action_taken is None
        assert "did not take any action" in second.response.lower()


class TestAgentRefundFlow:
    def test_refund_success(self, seeded_db):
        result = handle_agent_message(
            user_id="user_2",
            message="I want a refund for ORD-1003 because it arrived damaged",
            db=seeded_db,
        )

        assert result.action_taken == "request_refund"
        assert result.success is True
        assert "refund request submitted" in result.response.lower()

    def test_refund_missing_order_id(self, seeded_db):
        result = handle_agent_message(
            user_id="user_2",
            message="I want a refund because it arrived damaged",
            db = seeded_db,
        )

        assert result.success is False
        assert "order_id" in result.missing_fields

    def test_unknown_intent(self, seeded_db):
        result = handle_agent_message(
            user_id="user_2",
            message="What are your opening hours?",
            db=seeded_db,
        )

        assert result.success is False
        assert result.action_taken is None
