from fastapi import FastAPI

from app.api.routes import router
from app.db.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="E-commerce Order Operations Agent")

app.include_router(router)