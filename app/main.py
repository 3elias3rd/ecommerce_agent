from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.api.auth_routes import router as auth_router
from app.api.admin_routes import router as admin_router
from app.utils.rate_limiter import limiter
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ── Startup seeder ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.database import SessionLocal
    from app.db.models import Order
    from app.db.seed import seed

    db = SessionLocal()
    try:
        count = db.query(Order).count()
        if count == 0:
            logger.info("APP | startup | db_empty=true | seeding")
            seed()
        else:
            logger.info(f"APP | startup | db_empty=false | orders={count} | skipping_seed")
    except Exception as e:
        logger.warning(f"APP | startup | seed_check_failed | reason={e}")
    finally:
        db.close()

    yield  # app runs here


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="Order Ops Agent", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth_router)   # /auth/login       — public
app.include_router(admin_router)  # /admin/reset      — public, Swagger only
app.include_router(router)        # all other routes  — protected

# ── Frontend — must be last ───────────────────────────────────
app.mount("/", StaticFiles(directory="app/frontend", html=True), name="frontend")

logger.info("APP | started | routers=registered")