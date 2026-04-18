from app.db import create_user , get_user_by_email 
from app.core.security import get_password_hash
from app.core.config import get_settings
from app.models import User 
from app.schemas import UserCreate , UserResponse
from sqlalchemy.orm import Session




settings = get_settings()

def register_user(db: Session, user_create: UserCreate) -> UserResponse:
    """
    Register a new user with the given email and password.
    
    Raises a ValueError if the email is already registered.
    
    Returns the UserResponse object of the newly created user.
    """
    existing_user = get_user_by_email(db, user_create.email)
    if existing_user:
        raise ValueError("Email already registered")
    
    hashed_password = get_password_hash(user_create.password)
    user : User = create_user(
        db=db,
        user=user_create,
        hashed_password=hashed_password
        )
    return UserResponse.model_validate(user)


