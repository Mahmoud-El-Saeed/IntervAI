from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.db import save_refresh_token , get_user_by_email , get_refresh_token, get_user_by_id
from app.core.security import (create_refresh_token,
                               create_access_token,
                               verify_password,
                               decode_access_token)
from app.core.config import get_settings
from app.schemas import Token
from app.models import User, RefreshToken
from uuid import UUID

settings = get_settings()

def login_user(db: Session, email: str, password: str) -> Token:
    """
    Authenticate a user and return access and refresh tokens.
    
    Raises a ValueError if authentication fails.
    """
    user: User | None = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token: str = create_refresh_token()
    
    save_refresh_token(
        db=db,
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

def refresh_access_token(db: Session, refresh_token: str) -> Token:
    """
    Refresh the access token using a valid refresh token.
    
    Raises a ValueError if the refresh token is invalid or expired.
    """
    token_data: RefreshToken | None = get_refresh_token(db, refresh_token)
    if not token_data or token_data.expires_at < datetime.now(timezone.utc):
        raise ValueError("Invalid or expired refresh token")

    user: User | None = get_user_by_id(db, token_data.user_id)
    if not user:
        raise ValueError("User not found")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

def verify_token(db: Session, token: str) -> User | ValueError:
    """
    Verify the access token and return the associated user.
    
    Raises a ValueError if the token is invalid or expired.
    Returns the User object associated with the token if valid.
    """
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise ValueError("Invalid token: missing user ID")
        return get_user_by_id(db=db,user_id=UUID(user_id))
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")
    