from sqlalchemy.orm import Session
from app.models import User
from app.schemas import UserCreate
from uuid import UUID

def create_user(db: Session, user: UserCreate, hashed_password: str) -> User:
    """Create a new user in the database."""

    db_user = User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user) 
    return db_user

def get_user_by_email(db: Session, email: str) -> User | None:
    """Retrieve a user from the database by email."""
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    """Retrieve a user from the database by ID."""
    return db.query(User).filter(User.id == user_id).first()
