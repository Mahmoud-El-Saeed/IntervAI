from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.ai.graph import get_resume_analysis_graph
from app.core.analysis_logging import get_analysis_logger, quiet_external_loggers
from app.core.config import get_settings


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
        return payload

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
