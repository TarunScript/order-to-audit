"""Authentication, JWT tokens, and Role-Based Access Control (RBAC)."""
import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Callable, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.settings import settings
from app.models import User

# Secure password hashing via native bcrypt with PBKDF2 compatibility
try:
    import bcrypt
    def get_password_hash(password: str) -> str:
        pwd_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if hashed_password.startswith("$pbkdf2$"):
            parts = hashed_password.split("$")
            salt = parts[2]
            expected = parts[3]
            calculated = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100000).hex()
            return hmac.compare_digest(expected, calculated)
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False
except ImportError:
    def get_password_hash(password: str) -> str:
        salt = hashlib.sha256(str(time.time()).encode()).hexdigest()[:16]
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
        return f"$pbkdf2${salt}${h}"

    def verify_password(plain_password: str, hashed_password: str) -> bool:
        if not hashed_password.startswith("$pbkdf2$"):
            return plain_password == hashed_password
        parts = hashed_password.split("$")
        salt = parts[2]
        expected = parts[3]
        calculated = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt.encode(), 100000).hex()
        return hmac.compare_digest(expected, calculated)

# Graceful python-jose or pure-python JWT fallback
try:
    from jose import JWTError, jwt
    def encode_jwt(claims: dict, key: str, algorithm: str) -> str:
        return jwt.encode(claims, key, algorithm=algorithm)

    def decode_jwt(token: str, key: str, algorithms: list) -> dict:
        return jwt.decode(token, key, algorithms=algorithms)
except ImportError:
    class JWTError(Exception):
        pass

    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    def _b64url_decode(s: str) -> bytes:
        padding = 4 - (len(s) % 4)
        if padding != 4:
            s += "=" * padding
        return base64.urlsafe_b64decode(s.encode())

    def encode_jwt(claims: dict, key: str, algorithm: str = "HS256") -> str:
        header = {"typ": "JWT", "alg": "HS256"}
        h_bytes = _b64url_encode(json.dumps(header, separators=(",", ":"), default=str).encode())
        p_bytes = _b64url_encode(json.dumps(claims, separators=(",", ":"), default=str).encode())
        signing_input = f"{h_bytes}.{p_bytes}".encode()
        sig = hmac.new(key.encode(), signing_input, hashlib.sha256).digest()
        s_bytes = _b64url_encode(sig)
        return f"{h_bytes}.{p_bytes}.{s_bytes}"

    def decode_jwt(token: str, key: str, algorithms: list = None) -> dict:
        try:
            parts = token.split(".")
            if len(parts) != 3:
                raise JWTError("Invalid token segments")
            h_str, p_str, s_str = parts
            signing_input = f"{h_str}.{p_str}".encode()
            expected_sig = hmac.new(key.encode(), signing_input, hashlib.sha256).digest()
            actual_sig = _b64url_decode(s_str)
            if not hmac.compare_digest(expected_sig, actual_sig):
                raise JWTError("Signature verification failed")
            payload = json.loads(_b64url_decode(p_str).decode())
            if "exp" in payload and payload["exp"] < time.time():
                raise JWTError("Token expired")
            return payload
        except Exception as e:
            raise JWTError(str(e))


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_PREFIX}/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    user_id: int


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None
    user_id: Optional[int] = None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token containing subject and claims."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": int(expire.timestamp()), "iat": int(now.timestamp())})
    return encode_jwt(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency: validate JWT token and return active DB user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Could not validate credentials", "details": None},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_jwt(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.username == username)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INACTIVE_USER", "message": "User account is inactive", "details": None},
        )
    return user


def require_roles(*allowed_roles: str) -> Callable:
    """RBAC dependency factory that validates current user's role."""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FORBIDDEN",
                    "message": f"Operation not permitted for role '{current_user.role}'. Required: {list(allowed_roles)}",
                    "details": None,
                },
            )
        return current_user

    return role_checker
