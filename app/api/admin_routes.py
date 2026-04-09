from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.seed import reset_db
from app.utils.logger import get_logger

logger = get_logger(__name__)

# include_in_schema=True keeps it visible in Swagger /docs
# No auth dependency — intentionally open for test environment use
router = APIRouter(prefix="/admin", tags=["admin"])


@router.post(
    "/reset",
    summary="Reset test data",
    description=(
        "Wipes all orders and refund requests, re-seeds the database to its "
        "original test state, and clears all Redis session state.\n\n"
        "**Use this when all test orders have been actioned and you want to "
        "start fresh without redeploying.**\n\n"
        "⚠️ This is destructive and immediate — all current order state will be lost."
    ),
)
def admin_reset(db: Session = Depends(get_db)):
    logger.warning("ADMIN | action=reset_db | triggered")
    result = reset_db(db)
    logger.warning(
        f"ADMIN | action=reset_db | result=completed"
        f" | orders_seeded={result['orders_seeded']}"
        f" | session_state_cleared={result['session_state_cleared']}"
    )
    return result