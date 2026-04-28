from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from sqlalchemy import text

from app.ai.graph import get_interview_graph, get_resume_analysis_graph
from app.ai.helpers import normalize_interview_score
from app.ai.state import InterviewSessionState
from app.core.analysis_logging import get_analysis_logger, quiet_external_loggers
from app.core.config import get_settings
from app.database import SessionLocal
from app.db.interview_analysis_crud import (
    get_interview_analysis_by_interview_id,
    upsert_interview_analysis,
)
from app.db.interview_crud import (
    create_interview_answer,
    create_interview_question,
    get_interview_by_id_with_resume,
    update_interview_answer_feedback,
    update_interview_status,
)
from app.enums import InterviewStatus


logger = get_analysis_logger(__name__)
settings = get_settings()


def _safe_db_uri_preview(uri: str) -> str:
    if not uri:
        return "<empty-db-uri>"

    if "@" not in uri:
        return uri

    prefix, suffix = uri.split("@", 1)
    if "://" in prefix:
        scheme, credentials = prefix.split("://", 1)
        if ":" in credentials:
            username = credentials.split(":", 1)[0]
            return f"{scheme}://{username}:***@{suffix}"

    return "***"


def _compact_state_summary(state: dict[str, Any]) -> str:
    return (
        f"status={state.get('status', '-')}, "
        f"skills={len(state.get('extracted_skills', []))}, "
        f"matched={len(state.get('matched_skills', []))}, "
        f"missing={len(state.get('missing_skills', []))}, "
        f"projects={state.get('project_total_expected', 0)}, "
        f"progress={state.get('progress_message', '-')}, "
        f"persisted={state.get('analysis_persisted', False)}"
    )


class ResumeAnalysisInput(BaseModel):
    interview_id: str
    resume_id: str
    resume_path: str
    job_title: str
    job_description: str
    preferred_language: str


def _build_initial_state(input_data: ResumeAnalysisInput) -> dict:

    return {
        "interview_id": input_data.interview_id,
        "resume_id": input_data.resume_id,
        "resume_path": input_data.resume_path,
        "job_title": input_data.job_title,
        "job_description": input_data.job_description,
        "preferred_language": input_data.preferred_language,
        "status": "analysis_started",
        "analysis_persisted": False,
        "status_events": [],
        "progress_events": [],
        "extracted_skills": [],
        "job_requirements": [],
        "matched_skills": [],
        "missing_skills": [],
        "validation_issues": [],
        "validation_recommendations": [],
        "search_queries": [],
        "search_results": "",
        "market_summary": {},
        "market_analysis_completed": False,
        "project_readmes": {},
        "project_summaries": {},
        "project_errors": {},
        "project_total_expected": 0,
        "project_count_completed": 0,
        "progress_message": "Queued for analysis",
    }


def _analysis_payload_from_state(state: dict) -> dict:
    payload = state.get("final_analysis_payload")
    if payload:
        # Filter out fields not in InterviewAnalysis model
        allowed_fields = {
            "matched_skills", "missing_skills", "market_trends", "project_summaries",
            "overall_score", "technical_evaluation", "soft_skills_evaluation",
            "final_verdict", "learning_roadmap",
        }
        return {k: v for k, v in payload.items() if k in allowed_fields}

    return {
        "matched_skills": {"items": state.get("matched_skills", [])},
        "missing_skills": {"items": state.get("missing_skills", [])},
        "market_trends": state.get("market_summary", {}),
        "project_summaries": state.get("project_summaries", {}),
        "overall_score": None,
        "technical_evaluation": {
            "validation_issues": state.get("validation_issues", []),
            "validation_recommendations": state.get("validation_recommendations", []),
        },
        "soft_skills_evaluation": None,
        "final_verdict": state.get("progress_message", "Analysis completed"),
        "learning_roadmap": {
            "focus_areas": state.get("missing_skills", [])[:5],
            "prep_actions": state.get("validation_recommendations", [])[:5],
        },
    }


async def run_resume_analysis(input_data: ResumeAnalysisInput) -> dict:
    """Pure analysis function that invokes LangGraph and returns final payload."""
    quiet_external_loggers()

    state = _build_initial_state(input_data)
    config = {"configurable": {"thread_id": input_data.interview_id}}

    logger.info(
        "analysis workflow started (interview_id=%s, thread_id=%s)",
        input_data.interview_id,
        input_data.interview_id,
    )
    logger.info("initial state (%s)", _compact_state_summary(state))

    safe_db_uri = _safe_db_uri_preview(settings.DATABASE_URI_NO_PSYCOG)
    logger.info("checkpoint store ready (db=%s)", safe_db_uri)

    async with AsyncPostgresSaver.from_conn_string(settings.DATABASE_URI_NO_PSYCOG) as checkpointer:
        logger.info("checkpoint connection opened")
        graph = get_resume_analysis_graph(checkpointer)
        logger.info("graph execution started (interview_id=%s)", input_data.interview_id)
        final_state = await graph.ainvoke(state, config=config)
        logger.info(
            "graph execution finished (interview_id=%s, final_keys=%s)",
            input_data.interview_id,
            list(final_state.keys()),
        )

    analysis_payload = _analysis_payload_from_state(final_state)
    logger.info("analysis workflow completed (interview_id=%s)", input_data.interview_id)
    return analysis_payload


class InterviewAIService:
    _locks: dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, checkpoint_db_uri: str | None = None) -> None:
        self._checkpoint_db_uri = checkpoint_db_uri or settings.DATABASE_URI_NO_PSYCOG

    @staticmethod
    def _config(interview_id: UUID | str) -> dict[str, Any]:
        return {"configurable": {"thread_id": str(interview_id)}}

    @staticmethod
    def _initial_state(interview_data: dict[str, Any] | None = None) -> InterviewSessionState:
        analysis = interview_data.get("analysis", {}) if interview_data else {}
        project_summaries = analysis.get("project_summaries", {})
        
        resume = interview_data.get("resume", {}) if interview_data else {}
        
        return {
            "interview_data": interview_data or {},
            "project_summaries": project_summaries,
            "resume_text": resume.get("text", ""),
            "job_description": interview_data.get("job_description", "") if interview_data else "",
            "memory": "",
            "turn_index": 0,
            "recent_topics": [],
            "current_topic": "General",
            "current_question": "",
            "expected_answer": "",
            "hint_count": 0,
            "request_hint": False,
            "difficulty_level": "Medium",
            "chat_history": [],
            "interview_score": 0,
            "total_questions_asked": 0,
            "low_score_streak": 0,
            "current_relevance_score": 0,
            "force_move_next": False,
            "forced_penalty": 0,
            "feedback_on_previous_answer": "",
            "question_results": [],
            "is_complete": False,
            "human_response": "",
            "final_summary": "",
            "final_report": None,
        }

    @asynccontextmanager
    async def _graph_context(self):
        async with AsyncPostgresSaver.from_conn_string(self._checkpoint_db_uri) as checkpointer:
            yield get_interview_graph(checkpointer)

    async def _get_state_values(self, graph: Any, config: dict[str, Any]) -> dict[str, Any] | None:
        if hasattr(graph, "aget_state"):
            snapshot = await graph.aget_state(config)
        else:
            snapshot = await asyncio.to_thread(graph.get_state, config)

        if snapshot is None:
            return None
        values = getattr(snapshot, "values", None)
        if isinstance(values, dict):
            return values
        if isinstance(snapshot, dict):
            return snapshot
        return None

    async def _update_state(self, graph: Any, config: dict[str, Any], values: dict[str, Any]) -> None:
        if hasattr(graph, "aupdate_state"):
            await graph.aupdate_state(config, values)
            return
        await asyncio.to_thread(graph.update_state, config, values)

    @classmethod
    async def _get_interview_lock(cls, interview_id: str) -> asyncio.Lock:
        async with cls._locks_guard:
            lock = cls._locks.get(interview_id)
            if lock is None:
                lock = asyncio.Lock()
                cls._locks[interview_id] = lock
            return lock

    async def _load_interview_context(self, interview_id: UUID) -> dict[str, Any]:
        def _read() -> dict[str, Any]:
            db = SessionLocal()
            try:
                interview = get_interview_by_id_with_resume(db, interview_id)
                if interview is None:
                    raise ValueError("Interview not found.")

                logger.info("Interview loaded: id=%s, resume_id=%s, status=%s", 
                           interview.id, interview.resume_id, interview.status)
                logger.info("Resume: %s", interview.resume)
                if interview.resume:
                    logger.info("Resume extracted_data keys: %s", 
                               list(interview.resume.extracted_data.keys()) if interview.resume.extracted_data else "None")

                analysis = get_interview_analysis_by_interview_id(db, interview_id)
                analysis_payload: dict[str, Any] = {}
                if analysis is not None:
                    analysis_payload = {
                        "id": str(analysis.id),
                        "matched_skills": analysis.matched_skills,
                        "missing_skills": analysis.missing_skills,
                        "market_trends": analysis.market_trends,
                        "project_summaries": analysis.project_summaries,
                        "overall_score": analysis.overall_score,
                        "technical_evaluation": analysis.technical_evaluation,
                        "soft_skills_evaluation": analysis.soft_skills_evaluation,
                        "final_verdict": analysis.final_verdict,
                        "learning_roadmap": analysis.learning_roadmap,
                    }
                    logger.info("Analysis loaded: project_summaries=%s", analysis.project_summaries)

                return {
                    "id": str(interview.id),
                    "resume_id": str(interview.resume_id),
                    "job_title": interview.job_title,
                    "job_description": interview.job_description,
                    "preferred_language": interview.preferred_language,
                    "status": interview.status.value,
                    "analysis": analysis_payload,
                    "resume": {
                        "text": interview.resume.extracted_data.get("cv_text", "") 
                        if interview.resume and interview.resume.extracted_data else "",
                    },
                }
            finally:
                db.close()

        return await asyncio.to_thread(_read)

    async def _set_interview_status(self, interview_id: UUID, status: InterviewStatus) -> None:
        def _write() -> None:
            db = SessionLocal()
            try:
                update_interview_status(db, interview_id, status)
            finally:
                db.close()

        await asyncio.to_thread(_write)

    async def _reset_checkpoint_thread(self, thread_id: str) -> None:
        def _write() -> None:
            db = SessionLocal()
            try:
                db.execute(text("DELETE FROM checkpoint_writes WHERE thread_id = :thread_id"), {"thread_id": thread_id})
                db.execute(text("DELETE FROM checkpoint_blobs WHERE thread_id = :thread_id"), {"thread_id": thread_id})
                db.execute(text("DELETE FROM checkpoints WHERE thread_id = :thread_id"), {"thread_id": thread_id})
                db.commit()
            finally:
                db.close()

        await asyncio.to_thread(_write)

    async def _persist_question(
        self,
        interview_id: UUID,
        question_text: str,
        expected_answer: str,
    ) -> UUID | None:
        if not question_text.strip():
            return None

        def _write() -> UUID:
            db = SessionLocal()
            try:
                question = create_interview_question(
                    db,
                    interview_id=interview_id,
                    question_text=question_text,
                    expected_answer=expected_answer,
                    question_type="technical",
                )
                return question.id
            finally:
                db.close()

        return await asyncio.to_thread(_write)

    async def _persist_answer_placeholder(
        self,
        question_id: UUID,
        user_response: str,
    ) -> UUID:
        def _write() -> UUID:
            db = SessionLocal()
            try:
                answer = create_interview_answer(
                    db,
                    question_id=question_id,
                    user_response=user_response,
                    ai_feedback="",
                    score=0,
                    processing_time=0.0,
                )
                return answer.id
            finally:
                db.close()

        return await asyncio.to_thread(_write)

    async def _finalize_answer(
        self,
        answer_id: UUID,
        ai_feedback: str,
        score: int,
        processing_time: float,
    ) -> None:
        def _write() -> None:
            db = SessionLocal()
            try:
                update_interview_answer_feedback(
                    db,
                    answer_id=answer_id,
                    ai_feedback=ai_feedback,
                    score=score,
                    processing_time=processing_time,
                )
            finally:
                db.close()

        await asyncio.to_thread(_write)

    async def _persist_final_report(self, interview_id: UUID, final_report: dict[str, Any]) -> None:
        def _write() -> None:
            db = SessionLocal()
            try:
                analysis = get_interview_analysis_by_interview_id(db, interview_id)
                payload = {
                    "matched_skills": analysis.matched_skills if analysis else {"items": []},
                    "missing_skills": analysis.missing_skills if analysis else {"items": []},
                    "market_trends": analysis.market_trends if analysis else {},
                    "project_summaries": analysis.project_summaries if analysis else {},
                    "overall_score": normalize_interview_score(final_report.get("average_score", 0.0)),
                    "technical_evaluation": (analysis.technical_evaluation or {}) if analysis else {},
                    "soft_skills_evaluation": (analysis.soft_skills_evaluation or {}) if analysis else {},
                    "final_verdict": final_report.get("recommendation") or final_report.get("debrief"),
                    "learning_roadmap": (analysis.learning_roadmap or {}) if analysis else {},
                }

                technical = dict(payload.get("technical_evaluation") or {})
                technical["interview_report"] = {
                    "debrief": final_report.get("debrief", ""),
                    "average_score": normalize_interview_score(final_report.get("average_score", 0.0)),
                }
                payload["technical_evaluation"] = technical

                soft = dict(payload.get("soft_skills_evaluation") or {})
                soft["strengths"] = final_report.get("strengths", [])
                payload["soft_skills_evaluation"] = soft

                roadmap = dict(payload.get("learning_roadmap") or {})
                roadmap["focus_areas"] = final_report.get("focus_areas", [])
                payload["learning_roadmap"] = roadmap

                upsert_interview_analysis(db, interview_id, payload)
                update_interview_status(db, interview_id, InterviewStatus.COMPLETED)
            finally:
                db.close()

        await asyncio.to_thread(_write)

    @staticmethod
    def _response_payload(state_values: dict[str, Any] | None) -> dict[str, Any]:
        if not state_values:
            return {
                "is_initialized": False,
                "is_complete": False,
                "current_question": "",
                "chat_history": [],
                "hint": "",
                "last_hint": "",
                "last_feedback": "",
                "final_report": None,
                "final_summary": "",
                "score": {"total": 0, "asked": 0},
            }

        chat_history = state_values.get("chat_history", [])
        last_hint = ""
        last_feedback = ""
        for entry in reversed(chat_history):
            if not last_feedback and entry.get("role") == "ai_feedback":
                last_feedback = entry.get("content", "")
            if not last_hint and entry.get("role") == "ai_hint":
                last_hint = entry.get("content", "")
            if last_hint and last_feedback:
                break

        return {
            "is_initialized": True,
            "is_complete": state_values.get("is_complete", False),
            "current_question": state_values.get("current_question", ""),
            "chat_history": state_values.get("chat_history", []),
            "hint": "",
            "last_hint": last_hint,
            "last_feedback": last_feedback,
            "final_report": state_values.get("final_report"),
            "final_summary": state_values.get("final_summary", ""),
            "score": {
                "total": int(round(normalize_interview_score(state_values.get("interview_score", 0)))),
                "asked": state_values.get("total_questions_asked", 0),
            },
            "hint_count": state_values.get("hint_count", 0),
            "difficulty_level": state_values.get("difficulty_level", "Medium"),
            "current_topic": state_values.get("current_topic", "General"),
            "force_move_next": state_values.get("force_move_next", False),
            "forced_penalty": state_values.get("forced_penalty", 0),
        }

    async def start_interview(self, interview_id: UUID | str) -> dict[str, Any]:
        interview_uuid = UUID(str(interview_id))
        interview_key = str(interview_uuid)
        config = self._config(interview_key)
        quiet_external_loggers()

        lock = await self._get_interview_lock(interview_key)
        async with lock:
            async with self._graph_context() as graph:
                existing = await self._get_state_values(graph, config)
                if existing and existing.get("current_question"):
                    return self._response_payload(existing)

                try:
                    interview_data = await self._load_interview_context(interview_uuid)
                except Exception as e:
                    logger.error("Failed to load interview context: %s", e)
                    raise

                initial_state = self._initial_state(interview_data)
                
                try:
                    await graph.ainvoke(initial_state, config=config)
                except Exception as e:
                    logger.error("Graph invoke failed: %s", e)
                    raise
                    
                updated = await self._get_state_values(graph, config)
                logger.info("After invoke: updated keys: %s", updated.keys() if updated else "None")
                logger.info("After invoke: current_question: %s", updated.get("current_question") if updated else "None")

                if updated is not None:
                    await self._set_interview_status(interview_uuid, InterviewStatus.INTERVIEW_IN_PROGRESS)
                    await self._persist_question(
                        interview_uuid,
                        updated.get("current_question", ""),
                        updated.get("expected_answer", ""),
                    )
                return self._response_payload(updated)

    async def submit_answer(self, interview_id: UUID | str, answer: str) -> dict[str, Any]:
        interview_uuid = UUID(str(interview_id))
        interview_key = str(interview_uuid)
        config = self._config(interview_key)
        quiet_external_loggers()

        lock = await self._get_interview_lock(interview_key)
        async with lock:
            try:
                async with self._graph_context() as graph:
                    current_state = await self._get_state_values(graph, config)
                    logger.info("submit_answer: current_state keys: %s", current_state.keys() if current_state else "None")
                    logger.info("submit_answer: current_question: %s", current_state.get("current_question") if current_state else "None")
                    
                    if current_state is None or not current_state.get("current_question"):
                        raise ValueError("Interview session is not initialized.")

                    prev_question = current_state.get("current_question", "")
                    prev_asked = int(current_state.get("total_questions_asked", 0))
                    prev_score = int(current_state.get("interview_score", 0))
                    prev_hint_count = int(current_state.get("hint_count", 0))
                    prev_chat_len = len(current_state.get("chat_history", []))
                    prev_question_results_len = len(current_state.get("question_results", []))

                    question_id = await self._persist_question(
                        interview_uuid,
                        current_state.get("current_question", ""),
                        current_state.get("expected_answer", ""),
                    )
                    if question_id is None:
                        raise ValueError("No active question found for this interview.")

                    started_at = time.perf_counter()
                    answer_id = await self._persist_answer_placeholder(question_id, answer)

                    try:
                        await graph.ainvoke(Command(resume=answer), config=config)
                    except Exception as exc:
                        logger.warning(
                            "Command resume failed for interview_id=%s, falling back to state update: %s",
                            interview_key,
                            exc,
                        )
                        await self._update_state(graph, config, {"human_response": answer})
                        await graph.ainvoke(None, config=config)
                    updated = await self._get_state_values(graph, config)

                    if updated is None:
                        raise ValueError("Unable to read updated interview state.")

                    updated_asked = int(updated.get("total_questions_asked", 0))
                    updated_score = int(updated.get("interview_score", 0))
                    updated_hint_count = int(updated.get("hint_count", 0))
                    updated_chat = updated.get("chat_history", [])
                    updated_question_results = updated.get("question_results", [])

                    progressed = (
                        bool(updated.get("is_complete", False))
                        or updated_asked > prev_asked
                        or updated_score > prev_score
                        or updated.get("current_question", "") != prev_question
                        or updated_hint_count > prev_hint_count
                        or len(updated_chat) > prev_chat_len
                    )
                    if not progressed:
                        logger.warning(
                            "No interview progression detected after submit_answer "
                            "(interview_id=%s, asked=%s, score=%s)",
                            interview_key,
                            prev_asked,
                            prev_score,
                        )
                        raise ValueError("Interview did not advance after answer submission.")

                    ai_feedback = ""
                    score = 0
                    is_evaluated_turn = len(updated_question_results) > prev_question_results_len
                    new_messages = updated_chat[prev_chat_len:]
                    if is_evaluated_turn:
                        for entry in reversed(new_messages):
                            if entry.get("role") == "ai_feedback":
                                ai_feedback = entry.get("content", "")
                                break
                        if not ai_feedback:
                            for entry in reversed(updated_chat):
                                if entry.get("role") == "ai_feedback":
                                    ai_feedback = entry.get("content", "")
                                    break

                        if updated_question_results:
                            score = int(updated_question_results[-1].get("final_score", 0))
                    else:
                        for entry in reversed(new_messages):
                            if entry.get("role") == "ai_hint":
                                ai_feedback = entry.get("content", "")
                                break
                        if not ai_feedback:
                            ai_feedback = "Hint provided; awaiting refined answer."

                    elapsed = time.perf_counter() - started_at
                    await self._finalize_answer(answer_id, ai_feedback, score, elapsed)

                    if updated.get("is_complete", False):
                        report = updated.get("final_report") or {}
                        await self._persist_final_report(interview_uuid, report)
                    else:
                        await self._persist_question(
                            interview_uuid,
                            updated.get("current_question", ""),
                            updated.get("expected_answer", ""),
                        )
                    payload = self._response_payload(updated)
                    if not is_evaluated_turn and updated_hint_count > prev_hint_count:
                        payload["event_type"] = "hint_provided"
                        payload["hint"] = ai_feedback
                    return payload
            except Exception as exc:
                logger.exception("submit_answer failed for interview_id=%s", interview_key)
                return {
                    "event_type": "error",
                    "detail": str(exc) or "Interview processing failed.",
                }

    async def get_current_state(self, interview_id: UUID | str) -> dict[str, Any]:
        config = self._config(interview_id)
        quiet_external_loggers()

        async with self._graph_context() as graph:
            state_values = await self._get_state_values(graph, config)
            return self._response_payload(state_values)
