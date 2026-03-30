from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.routes import router
from app.db.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="E-commerce Order Operations Agent",
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router)