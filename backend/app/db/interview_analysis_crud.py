from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import InterviewAnalysis


def get_interview_analysis_by_interview_id(db: Session, interview_id: UUID) -> InterviewAnalysis | None:
    return db.query(InterviewAnalysis).filter(InterviewAnalysis.interview_id == interview_id).first()


def upsert_interview_analysis(db: Session, interview_id: UUID, payload: dict) -> InterviewAnalysis:
    analysis = get_interview_analysis_by_interview_id(db, interview_id)

    if analysis is None:
        analysis = InterviewAnalysis(interview_id=interview_id, **payload)
        db.add(analysis)
    else:
        for key, value in payload.items():
            setattr(analysis, key, value)

    db.commit()
    db.refresh(analysis)
    return analysis
