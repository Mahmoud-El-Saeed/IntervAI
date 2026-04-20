from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
    name: str = Field(default="")
    email: str = Field(default="")
    phone: str = Field(default="")


class Education(BaseModel):
    degree: str = Field(default="")
    institution: str = Field(default="")
    year: str = Field(default="")


class Experience(BaseModel):
    role: str = Field(default="")
    company: str = Field(default="")
    duration: str = Field(default="")


class ProjectLink(BaseModel):
    name: str = Field(default="")
    url: str = Field(default="")


class CVExtraction(BaseModel):
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    extracted_skills: list[str] = Field(default_factory=list)
    project_links: list[ProjectLink] = Field(default_factory=list)


class JobAlignmentOutput(BaseModel):
    job_requirements: list[str] = Field(default_factory=list)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class ValidationOutput(BaseModel):
    is_consistent: bool = Field(default=True)
    normalized_job_title: str = Field(default="")
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class SearchQueryList(BaseModel):
    queries: list[str] = Field(default_factory=list)


class SearchSummary(BaseModel):
    market_trends_2026: list[str] = Field(default_factory=list)
    expected_technical_questions: list[str] = Field(default_factory=list)
    tech_stack_updates: list[str] = Field(default_factory=list)


class ProjectDetail(BaseModel):
    tech_stack: list[str] = Field(default_factory=list)
    key_features: list[str] = Field(default_factory=list)
    potential_interview_questions: list[str] = Field(default_factory=list)


class FinalAnalysisPayload(BaseModel):
    matched_skills: dict[str, Any] = Field(default_factory=dict)
    missing_skills: dict[str, Any] = Field(default_factory=dict)
    market_trends: dict[str, Any] = Field(default_factory=dict)
    project_summaries: dict[str, Any] = Field(default_factory=dict)
    overall_score: float | None = None
    technical_evaluation: dict[str, Any] | None = None
    soft_skills_evaluation: dict[str, Any] | None = None
    final_verdict: str | None = None
    learning_roadmap: dict[str, Any] | None = None


class InterviewState(TypedDict, total=False):
    interview_id: str
    resume_id: str
    resume_path: str
    job_title: str
    job_description: str
    preferred_language: str

    status: str
    progress_message: str
    error_message: str
    analysis_persisted: bool

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

    project_name: str
    project_url: str
    readme_content: str
    readme_status: str
    project_readmes: Annotated[dict[str, str], operator.or_]
    project_summaries: Annotated[dict[str, dict[str, Any]], operator.or_]
    project_errors: Annotated[dict[str, str], operator.or_]
    project_total_expected: int
    project_count_completed: Annotated[int, operator.add]

    final_analysis_payload: dict[str, Any]
