from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class PersonalInfo(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""


class Education(BaseModel):
    degree: str = ""
    institution: str = ""
    year: str = ""


class Experience(BaseModel):
    role: str = ""
    company: str = ""
    duration: str = ""


class ProjectLink(BaseModel):
    name: str = ""
    url: str = ""


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
    is_consistent: bool = True
    normalized_job_title: str = ""
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
    overall_score_label: str = "Preliminary"
    technical_evaluation: dict[str, Any] | None = None
    soft_skills_evaluation: dict[str, Any] | None = None
    final_verdict: str | None = None
    learning_roadmap: dict[str, Any] | None = None
    phase: str = "phase_1"
    next_phase: str = "interview"


class NextQuestion(BaseModel):
    selected_topic: str = ""
    rationale: str = ""
    question: str = ""
    expected_answer: str = ""
    topic: str = ""
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"


class GreetingResult(BaseModel):
    greeting: str = ""


class AnalysisResult(BaseModel):
    category: Literal["Complete", "Partial", "Skipped"] = "Partial"
    relevance_score: int = 0
    internal_reasoning: str = ""


class EvaluationResult(BaseModel):
    acknowledgement: str = ""
    score: float = 0.0
    feedback: str = ""
    ideal_response_summary: str = ""


class FinalReportResult(BaseModel):
    debrief: str = ""
    recommendation: str = ""
    strengths: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    average_score: float = 0.0
    phase: str = "phase_2"
    phase_label: str = "Interview Assessment"
    combined_score: float | None = None
    combined_score_label: str | None = None


class ChatMessage(BaseModel):
    role: Literal["system", "ai", "human", "ai_hint", "ai_feedback", "report"]
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


class StrategyPlan(BaseModel):
    selected_topic: str = ""
    rationale: str = ""


class GeneratedQuestion(BaseModel):
    reasoning_skill_tested: str = ""
    reasoning_previous_gap: str = ""
    feedback_on_previous_answer: str = ""
    question_text: str = ""
    expected_answer: str = ""
    topic: str = ""
    difficulty: Literal["Easy", "Medium", "Hard"] = "Medium"


class AnswerAnalysis(BaseModel):
    category: Literal["Complete", "Partial", "Skipped"] = "Partial"
    relevance_score: int = 0
    internal_reasoning: str = ""


class HintOutput(BaseModel):
    acknowledgement: str = ""
    hint_text: str = ""


class EvaluatorOutput(BaseModel):
    acknowledgement: str = ""
    raw_score: int = 0
    feedback: str = ""
    ideal_response_summary: str = ""


class MemorySummaryOutput(BaseModel):
    memory: str = ""


class FinalReport(BaseModel):
    debrief: str = ""
    recommendation: str = ""
    strengths: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    average_score: float = 0.0