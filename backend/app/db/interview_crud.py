from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.enums import InterviewStatus
from app.models import Interview, InterviewAnswer, InterviewQuestion


def create_interview(
    db: Session,
    user_id: UUID,
    resume_id: UUID,
    job_title: str,
    job_description: str,
    preferred_language: str = "en",
) -> Interview:
    """Create a new interview in pending state."""
    new_interview = Interview(
        user_id=user_id,
        resume_id=resume_id,
        job_title=job_title,
        job_description=job_description,
        preferred_language=preferred_language,
        status=InterviewStatus.PENDING,
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)
    return new_interview


def get_all_interviews_for_user(db: Session, user_id: UUID) -> list[Interview]:
    """Retrieve all interviews for a specific user ordered by newest first."""
    return (
        db.query(Interview)
        .filter(Interview.user_id == user_id)
        .order_by(Interview.created_at.desc())
        .all()
    )


def get_interview_for_user(db: Session, interview_id: UUID, user_id: UUID) -> Interview | None:
    """Retrieve one interview if it belongs to the user."""
    return (
        db.query(Interview)
        .filter(Interview.id == interview_id, Interview.user_id == user_id)
        .first()
    )


def get_interview_details_for_user(db: Session, interview_id: UUID, user_id: UUID) -> Interview | None:
    """Retrieve one interview with analysis, questions, and answers if it belongs to the user."""
    return (
        db.query(Interview)
        .options(
            selectinload(Interview.analysis),
            selectinload(Interview.questions).selectinload(InterviewQuestion.answers),
        )
        .filter(Interview.id == interview_id, Interview.user_id == user_id)
        .first()
    )


def get_interview_by_id_with_resume(db: Session, interview_id: UUID) -> Interview | None:
    """Retrieve one interview with resume relationship loaded."""
    return (
        db.query(Interview)
        .options(selectinload(Interview.resume))
        .filter(Interview.id == interview_id)
        .first()
    )


def update_interview_status(
    db: Session, interview_id: UUID, status: InterviewStatus
) -> Interview | None:
    """Update interview lifecycle status."""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        return None

    interview.status = status
    db.commit()
    db.refresh(interview)
    return interview


def get_question_by_text(
    db: Session,
    interview_id: UUID,
    question_text: str,
) -> InterviewQuestion | None:
    return (
        db.query(InterviewQuestion)
        .filter(
            InterviewQuestion.interview_id == interview_id,
            InterviewQuestion.question_text == question_text,
        )
        .first()
    )


def create_interview_question(
    db: Session,
    interview_id: UUID,
    question_text: str,
    expected_answer: str,
    question_type: str = "technical",
) -> InterviewQuestion:
    existing = get_question_by_text(db, interview_id, question_text)
    if existing is not None:
        return existing

    question = InterviewQuestion(
        interview_id=interview_id,
        question_text=question_text,
        question_type=question_type,
        expected_answer=expected_answer,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def get_latest_interview_question(db: Session, interview_id: UUID) -> InterviewQuestion | None:
    return (
        db.query(InterviewQuestion)
        .filter(InterviewQuestion.interview_id == interview_id)
        .order_by(InterviewQuestion.id.desc())
        .first()
    )


def create_interview_answer(
    db: Session,
    question_id: UUID,
    user_response: str,
    ai_feedback: str,
    score: int,
    processing_time: float,
    audio_url: str | None = None,
) -> InterviewAnswer:
    answer = InterviewAnswer(
        question_id=question_id,
        user_response=user_response,
        ai_feedback=ai_feedback,
        score=score,
        processing_time=processing_time,
        audio_url=audio_url,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


def update_interview_answer_feedback(
    db: Session,
    answer_id: UUID,
    ai_feedback: str,
    score: int,
    processing_time: float,
) -> InterviewAnswer | None:
    answer = db.query(InterviewAnswer).filter(InterviewAnswer.id == answer_id).first()
    if answer is None:
        return None

    answer.ai_feedback = ai_feedback
    answer.score = score
    answer.processing_time = processing_time
    db.commit()
    db.refresh(answer)
    return answer