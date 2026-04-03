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


# ── User store ─────────────────────────────────────────────────

def _load_users() -> dict[str, str]:
    """
    Load users from flat AUTH_USER_N / AUTH_PASS_N env var pairs.
    This avoids JSON quote and $ character mangling on platforms like Koyeb.

    Set in your environment:
        AUTH_USER_1=tester1
        AUTH_PASS_1=$2b$12$...
        AUTH_USER_2=tester2
        AUTH_PASS_2=$2b$12$...
    """
    users: dict[str, str] = {}

    pairs = [
        (settings.auth_user_1, settings.auth_pass_1),
        (settings.auth_user_2, settings.auth_pass_2),
        (settings.auth_user_3, settings.auth_pass_3),
        (settings.auth_user_4, settings.auth_pass_4),
        (settings.auth_user_5, settings.auth_pass_5),
    ]

    for username, hashed in pairs:
        if username and hashed:
            users[username] = hashed

    if not users:
        logger.warning("AUTH | no_users_loaded | check AUTH_USER_N and AUTH_PASS_N env vars")
    else:
        logger.info(f"AUTH | users_loaded | count={len(users)}")

    return users


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