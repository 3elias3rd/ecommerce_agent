from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.utils.auth import authenticate_user, create_access_token
from app.utils.rate_limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest):
    if not authenticate_user(body.username, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(body.username)
    return TokenResponse(access_token=token)