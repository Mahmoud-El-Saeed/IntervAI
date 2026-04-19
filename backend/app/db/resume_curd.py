from app.models import Resume
from sqlalchemy.orm import Session
from uuid import UUID, uuid4

def create_resume(db: Session,resume_id: UUID, user_id: UUID, extracted_data: dict, file_path: str) -> Resume:
    """Create a new resume record in the database."""
    new_resume = Resume(
        id=resume_id,
        user_id=user_id,
        extracted_data=extracted_data,
        file_path=file_path
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    return new_resume

def get_resume_by_id(db: Session, resume_id: UUID) -> Resume | None:
    """Retrieve a resume by its ID."""
    return db.query(Resume).filter(Resume.id == resume_id).first()

def get_all_resumes_for_user(db: Session, user_id: UUID) -> list[Resume]:
    """Retrieve all resumes for a specific user."""
    return db.query(Resume).filter(Resume.user_id == user_id).all()