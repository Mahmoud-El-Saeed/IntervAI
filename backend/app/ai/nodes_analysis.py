"""LangGraph nodes for resume analysis workflow."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.core.loader import load_document_text
from .constants import (
    MAX_SEARCH_RESULTS,
    MAX_JD_LENGTH,
)
from .exceptions import (
    CVExtractionError,
    JobAlignmentError,
    ValidationError,
    MarketAnalysisError,
    ProjectFetchError,
)
from .helpers import (
    log_progress,
    project_links_to_map,
    generate_readme_urls,
    calculate_overall_score,
    build_final_verdict,
    derive_project_name_from_url,
    prepare_text_chunks_and_embeddings,
)
from .prompts import (
    SYSTEM_CV_EXTRACT,
    SYSTEM_JOB_ALIGN,
    SYSTEM_VALIDATION,
    SYSTEM_MARKET_QUERY,
    SYSTEM_MARKET_SUMMARY,
    SYSTEM_PROJECT_SUMMARY,
)
from .schemas import (
    CVExtraction,
    JobAlignmentOutput,
    ValidationOutput,
    SearchQueryList,
    SearchSummary,
    ProjectDetail,
    FinalAnalysisPayload,
)
from .services import (
    get_extraction_service,
    get_alignment_service,
    get_validation_service,
    get_query_service,
    get_summary_service,
    get_project_service,
    get_search_service,
    invoke_llm_chain,
    search_query,
    fetch_url,
    save_project_embeddings,
)
from .state import InterviewState, ProjectState

logger = logging.getLogger(__name__)


async def extract_cv_node(state: InterviewState) -> dict[str, Any]:
    """Extract structured CV data from resume text."""
    log_progress("extract_cv_node", f"Starting extraction for interview {state.get('interview_id')}")

    cv_text = await asyncio.to_thread(load_document_text, state["resume_path"])

    parser = JsonOutputParser(pydantic_object=CVExtraction)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_CV_EXTRACT + "\n{format_instructions}"),
            ("human", "{cv_text}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        extracted_raw = await invoke_llm_chain(
            prompt,
            parser,
            {"cv_text": cv_text},
            get_extraction_service(),
        )
        extracted = CVExtraction.model_validate(extracted_raw)

        log_progress("extract_cv_node", "Resume extraction completed")
        return {
            "status": "cv_extracted",
            "progress_message": "Resume extraction completed",
            "cv_text": cv_text,
            "personal_info": extracted.personal_info.model_dump(),
            "education": [item.model_dump() for item in extracted.education],
            "experience": [item.model_dump() for item in extracted.experience],
            "extracted_skills": extracted.extracted_skills,
            "project_links": project_links_to_map(extracted.project_links),
            "project_total_expected": len(extracted.project_links),
        }
    except Exception as e:
        raise CVExtractionError(f"CV extraction failed: {e}") from e


async def job_alignment_node(state: InterviewState) -> dict[str, Any]:
    """Align CV skills with job requirements."""
    log_progress("job_alignment_node", f"Aligning profile with {state.get('job_title')}")

    parser = JsonOutputParser(pydantic_object=JobAlignmentOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_JOB_ALIGN + "\n{format_instructions}"),
            ("human", "User Skills: {skills}\nJob Title: {title}\nJob Description: {description}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        alignment_raw = await invoke_llm_chain(
            prompt,
            parser,
            {
                "skills": state.get("extracted_skills", []),
                "title": state.get("job_title", ""),
                "description": state.get("job_description", "")[:MAX_JD_LENGTH],
            },
            get_alignment_service(),
        )
        alignment = JobAlignmentOutput.model_validate(alignment_raw)

        log_progress("job_alignment_node", "Alignment completed")
        return {
            "status": "job_aligned",
            "progress_message": "Job alignment completed",
            "job_requirements": alignment.job_requirements,
            "matched_skills": alignment.matched_skills,
            "missing_skills": alignment.missing_skills,
        }
    except Exception as e:
        raise JobAlignmentError(f"Job alignment failed: {e}") from e


async def validation_node(state: InterviewState) -> dict[str, Any]:
    """Validate job alignment consistency."""
    log_progress("validation_node", "Validating job alignment")

    parser = JsonOutputParser(pydantic_object=ValidationOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_VALIDATION + "\n{format_instructions}"),
            ("human", "Job Title: {title}\nRequirements: {requirements}\nMatched Skills: {matched}\nMissing Skills: {missing}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        validation_raw = await invoke_llm_chain(
            prompt,
            parser,
            {
                "title": state.get("job_title", ""),
                "requirements": state.get("job_requirements", []),
                "matched": state.get("matched_skills", []),
                "missing": state.get("missing_skills", []),
            },
            get_validation_service(),
        )
        validation = ValidationOutput.model_validate(validation_raw)

        issues = list(state.get("validation_issues", [])) + validation.issues
        recommendations = list(state.get("validation_recommendations", [])) + validation.recommendations

        if not validation.is_consistent:
            issues.append("Job alignment validation detected inconsistencies.")

        log_progress("validation_node", "Validation completed")
        return {
            "status": "validated",
            "progress_message": "Validation completed",
            "validation_issues": issues,
            "validation_recommendations": recommendations,
            "normalized_job_title": validation.normalized_job_title or state.get("job_title", ""),
        }
    except Exception as e:
        raise ValidationError(f"Validation failed: {e}") from e


async def market_intelligence_node(state: InterviewState) -> dict[str, Any]:
    """Generate market intelligence queries and execute searches."""
    log_progress("market_intelligence_node", "Generating market intelligence queries")

    parser = JsonOutputParser(pydantic_object=SearchQueryList)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_MARKET_QUERY + "\n{format_instructions}"),
            ("human", "Matched: {matched}\nMissing: {missing}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        query_results_raw = await invoke_llm_chain(
            prompt,
            parser,
            {
                "matched": state.get("matched_skills", []),
                "missing": state.get("missing_skills", []),
            },
            get_query_service(),
        )
        query_results = SearchQueryList.model_validate(query_results_raw)

        search_payloads: list[dict[str, Any]] = []
        for query in query_results.queries[:MAX_SEARCH_RESULTS]:
            try:
                result = await search_query(query, get_search_service())
                search_payloads.append({"query": query, "result": result})
            except Exception as exc:
                logger.exception("Tavily search failed for query %s", query)
                search_payloads.append({"query": query, "error": str(exc)})

        log_progress("market_intelligence_node", "Market search completed")
        return {
            "status_events": ["market_researched"],
            "progress_events": ["Market intelligence completed"],
            "search_queries": query_results.queries[:MAX_SEARCH_RESULTS],
            "search_results": json.dumps(search_payloads, default=str),
            "market_analysis_completed": True,
        }
    except Exception as e:
        raise MarketAnalysisError(f"Market intelligence failed: {e}") from e


async def market_summary_node(state: InterviewState) -> dict[str, Any]:
    """Summarize market intelligence into a report."""
    log_progress("market_summary_node", "Summarizing market intelligence")

    parser = JsonOutputParser(pydantic_object=SearchSummary)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_MARKET_SUMMARY + "\n{format_instructions}"),
            ("human", "Missing Skills: {missing}\n\nRaw Search Data: {data}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        summary_raw = await invoke_llm_chain(
            prompt,
            parser,
            {
                "missing": state.get("missing_skills", []),
                "data": state.get("search_results", ""),
            },
            get_summary_service(),
        )
        summary = SearchSummary.model_validate(summary_raw)

        market_summary = {
            "market_trends_2026": summary.market_trends_2026,
            "expected_technical_questions": summary.expected_technical_questions,
            "tech_stack_updates": summary.tech_stack_updates,
        }

        log_progress("market_summary_node", "Market summarization completed")
        return {
            "status_events": ["market_summarized"],
            "progress_events": ["Market intelligence summarized"],
            "market_summary": market_summary,
        }
    except Exception as e:
        raise MarketAnalysisError(f"Market summarization failed: {e}") from e


async def project_fetch_readme_node(state: ProjectState) -> dict[str, Any]:
    project_name = state.get("project_name", "").strip()
    project_url = state.get("project_url", "").strip()

    if not project_name:
        return {}

    readme_text = ""
    readme_status = "No README found"
    for candidate_url in generate_readme_urls(project_url):
        try:
            readme_text = await fetch_url(candidate_url)
            readme_status = "README fetched"
            break
        except Exception:
            logger.info("README not available at %s", candidate_url)

    if not readme_text:
        readme_status = "README unavailable"

    log_progress("project_fetch_readme_node", f"README status: {readme_status}")
    return {
        "readmes_status": {project_name: readme_status},
        "project_readmes": {project_name: readme_text},
        "readme_content": readme_text, 
        "project_count_completed": 1,
    }


async def project_summary_node(state: ProjectState) -> dict[str, Any]:
    """Summarize project README contents."""
    
    project_name = state.get("project_name", "").strip()

    readme_content = state.get("readme_content", "")
    
    log_progress("project_summary_node", f"Summarizing project {project_name}")
    

    if not readme_content.strip():
        summary = {
            "tech_stack": [],
            "key_features": [],
            "potential_interview_questions": [],
            "readme_status": "No README found",
            "note": "README content was not available for summarization.",
        }
    else:
        try:
            parser = JsonOutputParser(pydantic_object=ProjectDetail)
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROJECT_SUMMARY + "\n{format_instructions}"),
                    ("human", "Project: {name}\nContent: {content}"),
                ]
            ).partial(format_instructions=parser.get_format_instructions())

            details_raw = await invoke_llm_chain(
                prompt,
                parser,
                {"name": project_name, "content": readme_content},
                get_project_service(),
            )
            details = ProjectDetail.model_validate(details_raw)
            summary = {
                "tech_stack": details.tech_stack,
                "key_features": details.key_features,
                "potential_interview_questions": details.potential_interview_questions,
                "readme_status": "README fetched",
            }
        except Exception as exc:
            logger.exception("Error summarizing project %s", project_name)
            summary = {
                "tech_stack": [],
                "key_features": [],
                "potential_interview_questions": [],
                "readme_status": "README unavailable",
                "error": str(exc),
            }
    if readme_content.strip() and "error" not in summary:
        try:
            resume_id = state.get("resume_id")
            if resume_id:
                prefix = f"Project '{project_name}' README"
                chunks, embeddings = prepare_text_chunks_and_embeddings(readme_content, prefix)
                
                await asyncio.to_thread(
                    save_project_embeddings,
                    resume_id,
                    chunks,
                    embeddings
                )
                log_progress("project_summary_node", f"Ingested {len(chunks)} chunks for project {project_name}")
        except Exception as e:
            log_progress("project_summary_node", f"Embedding ingestion failed for {project_name}: {e}")
            
    log_progress("project_summary_node", f"Project summary completed for {project_name}")
    return {
        "status_events": ["project_summarized"],
        "progress_events": [f"Project summary completed for {project_name}"],
        "project_summaries": {project_name: summary},
        "project_errors": {project_name: summary["error"]} if "error" in summary else {},
        "project_count_completed": 1,
    }


async def finalize_analysis_node(state: InterviewState) -> dict[str, Any]:
    """Assemble final analysis payload when all components are ready."""
    project_total_expected = int(state.get("project_total_expected", 0) or 0)
    project_completed = int(state.get("project_count_completed", 0) or 0)
    market_ready = bool(state.get("market_analysis_completed", False))

    if not market_ready or (project_total_expected > 0 and project_completed < project_total_expected):
        return {}

    if state.get("final_analysis_payload"):
        return {}

    matched = state.get("matched_skills", [])
    missing = state.get("missing_skills", [])
    score = calculate_overall_score(matched, missing)
    verdict = build_final_verdict(score)

    final_payload = FinalAnalysisPayload(
        matched_skills={"items": matched},
        missing_skills={"items": missing},
        market_trends=state.get("market_summary", {}),
        project_summaries=state.get("project_summaries", {}),
        overall_score=score,
        overall_score_label="Preliminary - Based on CV",
        technical_evaluation={
            "validation_issues": state.get("validation_issues", []),
            "validation_recommendations": state.get("validation_recommendations", []),
            "job_requirements": state.get("job_requirements", []),
        },
        soft_skills_evaluation={"communication": "not assessed", "collaboration": "not assessed"},
        final_verdict=verdict,
        learning_roadmap={
            "focus_areas": missing[:5],
            "prep_actions": state.get("validation_recommendations", [])[:5],
        },
        phase="phase_1",
        next_phase="interview",
    )

    log_progress("finalize_analysis_node", "Analysis payload assembled")
    return {
        "status_events": ["analysis_ready"],
        "progress_events": ["Final analysis payload ready"],
        "final_analysis_payload": final_payload.model_dump(),
    }