"""State definitions for LangGraph workflows."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from .schemas import (
    AnalysisResult,
    ChatMessage,
    Education,
    Experience,
    FinalAnalysisPayload,
    FinalReportResult,
    PersonalInfo,
    ProjectLink,
    StrategyPlan,
)


class InterviewState(TypedDict, total=False):
    """State for resume analysis and interview flows."""

    interview_id: str
    resume_id: Annotated[str, lambda a, b: b]
    resume_path: str
    job_title: str
    job_description: str
    preferred_language: str

    status: str
    progress_message: str
    status_events: Annotated[list[str], operator.add]
    progress_events: Annotated[list[str], operator.add]
    error_message: str

    cv_text: str
    personal_info: dict[str, str]
    education: list[dict[str, str]]
    experience: list[dict[str, str]]
    extracted_skills: Annotated[list[str], operator.add]
    project_links: dict[str, str]

    job_requirements: Annotated[list[str], operator.add]
    matched_skills: Annotated[list[str], operator.add]
    missing_skills: Annotated[list[str], operator.add]

    validation_issues: Annotated[list[str], operator.add]
    validation_recommendations: Annotated[list[str], operator.add]
    normalized_job_title: str

    search_queries: list[str]
    search_results: str
    market_summary: dict[str, Any]
    market_analysis_completed: bool

    readmes_status: Annotated[dict[str, str], operator.or_]
    project_readmes: Annotated[dict[str, str], operator.or_]
    project_summaries: Annotated[dict[str, dict[str, Any]], operator.or_]
    project_errors: Annotated[dict[str, str], operator.or_]
    project_total_expected: int
    project_count_completed: Annotated[int, operator.add]

    final_analysis_payload: Annotated[dict[str, Any], operator.or_]


class InterviewSessionState(TypedDict, total=False):
    """State for interactive interview flow."""

    interview_data: dict[str, Any]
    resume_text: str
    job_title: str
    job_description: str
    preferred_language: str
    job_requirements: list[str]
    matched_skills: list[str]
    missing_skills: list[str]
    memory: str
    turn_index: int
    is_first_turn: bool
    pending_greeting: str
    recent_topics: Annotated[list[str], operator.add]
    current_topic: str
    current_question: str
    expected_answer: str
    hint_count: int
    hint_counter: int
    difficulty_level: str
    chat_history: Annotated[list[dict[str, Any]], operator.add]
    full_transcript: Annotated[list[str], operator.add]
    interview_score: float
    total_questions_asked: int
    low_score_streak: int
    current_relevance_score: int
    force_move_next: bool
    forced_penalty: int
    feedback_on_previous_answer: str
    question_results: Annotated[list[dict[str, Any]], operator.add]
    is_complete: bool
    human_response: str
    final_summary: str
    final_report: dict[str, Any] | None
    request_hint: bool

    strategy: dict[str, Any]
    status: str
    progress_message: str

    asked_questions: Annotated[list[str], operator.add]
    answers: Annotated[list[str], operator.add]
    analysis: Annotated[list[dict[str, Any]], operator.add]
    question_count: int

    evaluation: Annotated[list[dict[str, Any]], operator.add]

    project_summaries: dict[str, dict[str, Any]]
    potential_project_questions: Annotated[list[str], operator.add]
    project_questions_asked: Annotated[list[str], operator.add]
    

class ProjectState(TypedDict, total=False):
    """Private state for a single project's fetch+summarize pipeline."""
    # Inputs from Send
    project_name: str
    project_url: str
    resume_id: Annotated[str, lambda a, b: b] # last write wins

    # Internal
    readme_content: str

    # Outputs merged back into InterviewState
    readmes_status: Annotated[dict[str, str], operator.or_]
    project_readmes: Annotated[dict[str, str], operator.or_]
    project_summaries: Annotated[dict[str, dict[str, Any]], operator.or_]
    project_errors: Annotated[dict[str, str], operator.or_]
    project_count_completed: Annotated[int, operator.add]
    status_events: Annotated[list[str], operator.add]
    progress_events: Annotated[list[str], operator.add]
