from sqlalchemy.orm import Session
from app.models import RefreshToken
from uuid import UUID   
from datetime import datetime, timezone

def save_refresh_token(db: Session, user_id: UUID, token: str, expires_at: datetime) -> RefreshToken:
    """Create a new refresh token in the database."""
    db_token = RefreshToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token) 
    return db_token

def get_refresh_token(db: Session, token: str) -> RefreshToken | None:
    """Retrieve a refresh token from the database by token string."""
    refresh_token: RefreshToken=  db.query(RefreshToken).filter(RefreshToken.token == token).first()
    if not refresh_token:
        return None
    if  refresh_token.is_revoked or \
        refresh_token.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return None
    return refresh_token

def revoke_refresh_token(db: Session, token: str) -> None:
    """Revoke a refresh token by deleting it from the database."""
    db_token = get_refresh_token(db, token)
    if db_token:
        db.delete(db_token)
        db.commit()