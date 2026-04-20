from __future__ import annotations

import logging
from pydantic import BaseModel

from app.ai.graph import get_resume_analysis_graph


logger = logging.getLogger(__name__)


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
    graph = get_resume_analysis_graph()

    state = _build_initial_state(input_data)
    config = {"configurable": {"thread_id": input_data.interview_id}}

    logger.info("Starting resume analysis workflow for interview %s", input_data.interview_id)
    final_state = await graph.ainvoke(state, config=config)

    analysis_payload = _analysis_payload_from_state(final_state)
    logger.info("Completed resume analysis workflow for interview %s", input_data.interview_id)
    return analysis_payload
