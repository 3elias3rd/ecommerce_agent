import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
import bcrypt

from app.utils.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Password hashing ───────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── User store (loaded from AUTH_USERS env var) ────────────────

def _load_users() -> dict[str, str]:
    """
    Load users from AUTH_USERS env var.
    Expected format: JSON string of {username: hashed_password}
    e.g. {"tester1": "$2b$12$...", "tester2": "$2b$12$..."}
    """
    raw = settings.auth_users
    if not raw:
        logger.warning("AUTH | auth_users not set | no users will be able to login")
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(f"AUTH | failed to parse auth_users | reason={e}")
        return {}


# Load once at startup
_USERS: dict[str, str] = _load_users()


def authenticate_user(username: str, password: str) -> bool:
    """Return True if username exists and password matches."""
    hashed = _USERS.get(username)
    if not hashed:
        logger.warning(f"AUTH | login_failed | reason=user_not_found | username={username}")
        return False
    if not verify_password(password, hashed):
        logger.warning(f"AUTH | login_failed | reason=wrong_password | username={username}")
        return False
    logger.info(f"AUTH | login_success | username={username}")
    return True


# ── JWT ───────────────────────────────────────────────────────

def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": username, "exp": expire}
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    logger.info(f"AUTH | token_created | username={username} | expires_minutes={settings.access_token_expire_minutes}")
    return token


def decode_token(token: str) -> Optional[str]:
    """Decode and validate a JWT. Returns username or None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        username: str = payload.get("sub")
        if not username:
            return None
        return username
    except JWTError:
        return None