from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.core.config import get_settings

from .nodes import (
    extract_cv_node,
    finalize_analysis_node,
    job_alignment_node,
    market_intelligence_node,
    market_summary_node,
    project_fetch_readme_node,
    project_summary_node,
    validation_node,
)
from .state import InterviewState


logger = logging.getLogger(__name__)
settings = get_settings()


def _route_after_validation(state: InterviewState) -> list[str | Send]:
    destinations: list[str | Send] = ["market_intelligence"]
    project_links = state.get("project_links", {})
    for project_name, project_url in project_links.items():
        destinations.append(
            Send(
                "project_fetch_readme",
                {
                    "project_name": project_name,
                    "project_url": project_url,
                    "readme_content": "",
                    "readme_status": "pending",
                },
            )
        )
    return destinations


def _build_graph() -> StateGraph[InterviewState]:
    builder = StateGraph(InterviewState)

    builder.add_node("extract_cv", extract_cv_node)
    builder.add_node("align_job", job_alignment_node)
    builder.add_node("validate_alignment", validation_node)
    builder.add_node("market_intelligence", market_intelligence_node)
    builder.add_node("market_summary", market_summary_node)
    builder.add_node("project_fetch_readme", project_fetch_readme_node)
    builder.add_node("project_summary", project_summary_node)
    builder.add_node("finalize_analysis", finalize_analysis_node)

    builder.add_edge(START, "extract_cv")
    builder.add_edge("extract_cv", "align_job")
    builder.add_edge("align_job", "validate_alignment")
    builder.add_conditional_edges("validate_alignment", _route_after_validation)
    builder.add_edge("market_intelligence", "market_summary")
    builder.add_edge("market_summary", "finalize_analysis")
    builder.add_edge("project_fetch_readme", "project_summary")
    builder.add_edge("project_summary", "finalize_analysis")
    builder.add_edge("finalize_analysis", END)

    return builder


@lru_cache(maxsize=1)
def get_resume_analysis_graph():
    builder = _build_graph()
    checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URI)
    checkpointer.setup()
    logger.info("Resume analysis graph compiled with Postgres checkpointing")
    return builder.compile(checkpointer=checkpointer)
