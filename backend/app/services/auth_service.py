from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.db import save_refresh_token , get_user_by_email 
from app.core.security import create_refresh_token , create_access_token
from app.core.config import get_settings
from app.schemas import Token
from app.models import User

settings = get_settings()

def login_user(db: Session, email: str, password: str) -> Token:
    """
    Authenticate a user and return access and refresh tokens.
    
    Raises a ValueError if authentication fails.
    """
    user: User | None = get_user_by_email(db, email)
    if not user or not user.verify_password(password):
        raise ValueError("Invalid email or password")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=access_token_expires
    )
    refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token: str = create_refresh_token()
    
    save_refresh_token(
        db=db,
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc) + refresh_token_expires
    )
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )