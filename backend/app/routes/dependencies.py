from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth import verify_token
from app.database import get_db
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User | HTTPException:
    """
    Get the current authenticated user based on the provided access token.
    
    Raises an HTTPException with status code 401 if the token is invalid or expired.
    Returns the User object of the authenticated user.
    """
    try:
        return verify_token(db=db, token=token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )