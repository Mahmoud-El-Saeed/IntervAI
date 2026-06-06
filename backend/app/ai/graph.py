"""LangGraph workflow builders."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from .constants import MAX_QUESTIONS, RELEVANCE_HINT_THRESHOLD
from .nodes_analysis import (
    extract_cv_node,
    job_alignment_node,
    validation_node,
    market_intelligence_node,
    market_summary_node,
    project_fetch_readme_node,
    project_summary_node,
    finalize_analysis_node,
)
from .nodes_interview import (
    greeting_node,
    strategy_node,
    question_generator_node,
    human_input_node,
    analyzer_node,
    hint_node,
    evaluator_node,
    generate_final_report_node,
    summarize_history_node,
)
from .state import InterviewState, InterviewSessionState, ProjectState


logger = logging.getLogger(__name__)

def _build_project_subgraph() -> StateGraph:
    """Isolated fetch+summarize pipeline for one project."""
    builder = StateGraph(ProjectState)
    builder.add_node("project_fetch_readme", project_fetch_readme_node)
    builder.add_node("project_summary", project_summary_node)
    builder.add_edge(START, "project_fetch_readme")
    builder.add_edge("project_fetch_readme", "project_summary")
    builder.add_edge("project_summary", END)
    return builder.compile()


def route_after_validation(state: InterviewState) -> list[str | Send]:
    """Route after validation to market intelligence and parallel project fetching."""
    destinations: list[str | Send] = ["market_intelligence"]
    project_links = state.get("project_links", {})
    cv_text = state.get("cv_text", "")
    resume_id = state.get("resume_id", "")

    for project_name, project_url in project_links.items():
        destinations.append(
            Send(
                "project_pipeline",  
                {
                    "project_name": project_name,
                    "project_url": project_url,
                    "resume_id": resume_id,
                },
            )
        )
    return destinations



def _build_graph() -> StateGraph[InterviewState]:
    """Build resume analysis graph."""
    builder = StateGraph(InterviewState)

    builder.add_node("extract_cv", extract_cv_node)
    builder.add_node("align_job", job_alignment_node)
    builder.add_node("validate_alignment", validation_node)
    builder.add_node("market_intelligence", market_intelligence_node)
    builder.add_node("market_summary", market_summary_node)
    builder.add_node("project_pipeline", _build_project_subgraph())  
    builder.add_node("finalize_analysis", finalize_analysis_node)

    builder.add_edge(START, "extract_cv")
    builder.add_edge("extract_cv", "align_job")
    builder.add_edge("align_job", "validate_alignment")
    builder.add_conditional_edges("validate_alignment", route_after_validation)
    builder.add_edge("market_intelligence", "market_summary")
    builder.add_edge("market_summary", "finalize_analysis")
    builder.add_edge("project_pipeline", "finalize_analysis")
    builder.add_edge("finalize_analysis", END)

    return builder


def route_after_analyzer(state: InterviewSessionState) -> str:
    """Route based on relevance score to hint or evaluator."""
    if state.get("request_hint", False):
        return "hint_node"
    relevance = state.get("current_relevance_score", 0)
    if relevance < RELEVANCE_HINT_THRESHOLD:
        return "hint_node"
    return "evaluator_node"


def route_after_hint(state: InterviewSessionState) -> str:
    """Route after hint - always go to evaluator for scoring."""
    if state.get("force_move_next", False):
        return "evaluator_node"
    return "human_input_node"


def route_after_evaluation(state: InterviewSessionState) -> str:
    """Route after evaluation based on question count."""
    if state.get("total_questions_asked", state.get("question_count", 0)) >= MAX_QUESTIONS:
        return "generate_final_report_node"
    
    turn_index = state.get("turn_index", 0)
    
    if (turn_index + 1) % 3 == 0 and turn_index > 0:
        return "summarize_node" 
    
    return "question_generator_node"


def _build_interview_graph() -> StateGraph[InterviewSessionState]:
    """Build interactive interview graph."""
    builder = StateGraph(InterviewSessionState)

    builder.add_node("greeting_node", greeting_node)
    builder.add_node("strategy_node", strategy_node)
    builder.add_node("question_generator_node", question_generator_node)
    builder.add_node("human_input_node", human_input_node)
    builder.add_node("analyzer_node", analyzer_node)
    builder.add_node("hint_node", hint_node)
    builder.add_node("summarize_node", summarize_history_node)
    builder.add_node("evaluator_node", evaluator_node)
    builder.add_node("generate_final_report_node", generate_final_report_node)

    builder.add_edge(START, "greeting_node")
    builder.add_edge("greeting_node", "strategy_node")
    builder.add_edge("strategy_node", "question_generator_node")
    # After question_generator, graph ends and waits for frontend to submit answer
    # The submit_answer flow will resume from human_input_node
    builder.add_edge("question_generator_node", "human_input_node")
    builder.add_edge("human_input_node", "analyzer_node")
    builder.add_conditional_edges("analyzer_node", route_after_analyzer)
    builder.add_conditional_edges("hint_node", route_after_hint)
    builder.add_conditional_edges("evaluator_node", route_after_evaluation)
    builder.add_edge("summarize_node", "question_generator_node")
    builder.add_edge("generate_final_report_node", END)

    return builder


def get_resume_analysis_graph(checkpointer: Any):
    """Compile resume analysis graph with checkpointer."""
    builder = _build_graph()
    logger.info("Resume analysis graph compiled with database checkpointer")
    return builder.compile(checkpointer=checkpointer)


def get_interview_graph(checkpointer: Any):
    """Compile interview graph with checkpointer."""
    builder = _build_interview_graph()
    logger.info("Interview graph compiled with persistent checkpointer")
    return builder.compile(checkpointer=checkpointer)