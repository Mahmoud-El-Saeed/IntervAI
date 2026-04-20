from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any

import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.loader import load_document_text
from app.core.config import get_settings
import os

from .state import (
    CVExtraction,
    FinalAnalysisPayload,
    InterviewState,
    JobAlignmentOutput,
    ProjectDetail,
    SearchQueryList,
    SearchSummary,
    ValidationOutput,
)

settings = get_settings()

logger = logging.getLogger(__name__)
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY
os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY

llm_smart = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
llm_fast = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)

search_tool = TavilySearch(max_results=3)


def _log_progress(node_name: str, message: str, level: int = logging.INFO) -> None:
    """
    Centralized logging for node progress updates, including interview ID context when available.
    Logs are structured to include the node name and a clear progress message.
    """
    logger.log(level, "%s | %s", node_name, message)


def _project_links_to_map(project_links: Iterable[dict[str, str]] | Iterable[Any]) -> dict[str, str]:
    """
    Convert a list of project link objects (which may be dicts or Pydantic models) 
    into a standardized dictionary mapping project names to URLs.
    This function is defensive and handles both dicts and objects with attributes,
    ensuring that missing or malformed entries are skipped gracefully.
    """
    
    project_map: dict[str, str] = {}
    for project in project_links:
        if isinstance(project, dict):
            name = str(project.get("name", "")).strip()
            url = str(project.get("url", "")).strip()
        else:
            name = str(getattr(project, "name", "")).strip()
            url = str(getattr(project, "url", "")).strip()

        if name and url:
            project_map[name] = url

    return project_map


def _github_raw_readme_urls(project_url: str) -> list[str]:
    """
    Generate potential raw README URLs for a given GitHub project URL.
    This function normalizes the input URL and constructs candidate raw content URLs
    for both 'main' and 'master' branches, which are common default branches for GitHub repositories.
    If the URL does not appear to be a GitHub URL, it returns an empty list,
    allowing the caller to handle non-GitHub projects appropriately.
    """
    
    normalized_url = project_url.strip().rstrip("/")
    if not normalized_url.startswith(("http://", "https://")):
        normalized_url = f"https://{normalized_url}"

    if "github.com" not in normalized_url:
        return []

    raw_base = normalized_url.replace("https://github.com/", "https://raw.githubusercontent.com/")
    raw_base = raw_base.replace("http://github.com/", "https://raw.githubusercontent.com/")
    return [
        f"{raw_base}/main/README.md",
        f"{raw_base}/master/README.md",
    ]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def _load_resume_text(resume_path: str) -> str:
    """
    Load resume text from a given file path, supporting PDF and DOCX formats.
    Reuses the centralized load_document_text from app.core.loader.
    """
    return await asyncio.to_thread(load_document_text, resume_path)


async def _invoke_json_chain(
    prompt: ChatPromptTemplate,
    parser: JsonOutputParser,
    payload: dict[str, Any],
    model: ChatGroq,
) -> dict[str, Any]:
    
    chain = prompt | model.bind(response_format={"type": "json_object"}) | parser
    return await chain.ainvoke(payload)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def _invoke_llm_chain(
    prompt: ChatPromptTemplate,
    parser: JsonOutputParser,
    payload: dict[str, Any],
    model: ChatGroq,
) -> dict[str, Any]:
    """
    Invoke a LangChain prompt with a JSON output parser, applying retry logic for transient errors.
    """
    return await _invoke_json_chain(prompt, parser, payload, model)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def _tavily_search(query: str) -> Any:
    """
    Perform a search using the TavilySearch tool, with retry logic for transient errors.
    Use asyncio.to_thread to run the synchronous search method without blocking the event loop.
    """
    
    return await asyncio.to_thread(search_tool.invoke, {"query": query})


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=6),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def _fetch_url(url: str) -> str:
    """
    Fetch the content of a URL using an asynchronous HTTP client, with retry logic for transient errors.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def _build_final_payload(state: InterviewState) -> FinalAnalysisPayload:

    market_summary = state.get("market_summary", {})
    project_summaries = state.get("project_summaries", {})
    validation_issues = state.get("validation_issues", [])
    validation_recommendations = state.get("validation_recommendations", [])

    matched_skills = state.get("matched_skills", [])
    missing_skills = state.get("missing_skills", [])

    overall_score = max(0.0, min(100.0, 100.0 - (len(missing_skills) * 7.5) + (len(matched_skills) * 2.5)))
    final_verdict = "Strong match" if overall_score >= 75 else "Partial match; improve the missing skills"

    return FinalAnalysisPayload(
        matched_skills={"items": matched_skills},
        missing_skills={"items": missing_skills},
        market_trends=market_summary,
        project_summaries=project_summaries,
        overall_score=overall_score,
        technical_evaluation={
            "validation_issues": validation_issues,
            "validation_recommendations": validation_recommendations,
            "job_requirements": state.get("job_requirements", []),
        },
        soft_skills_evaluation={
            "communication": "not assessed",
            "collaboration": "not assessed",
        },
        final_verdict=final_verdict,
        learning_roadmap={
            "focus_areas": missing_skills[:5],
            "prep_actions": validation_recommendations[:5],
        },
    )


async def extract_cv_node(state: InterviewState) -> dict[str, Any]:
    """
    Extract structured CV data from the resume text using an LLM chain.
        - Loads the resume text from the provided file path.
        - Constructs a prompt with system instructions for CV extraction.
        - Invokes the LLM chain to extract personal info, education, experience, skills, and project links.
        - Logs progress at the start and completion of the extraction process.
    """
    _log_progress("extract_cv_node", f"Starting extraction for interview {state.get('interview_id')}")
    cv_text = await _load_resume_text(state["resume_path"])

    system_prompt = """
    You are an expert technical recruiter.
    Extract structured CV data from the resume text.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=CVExtraction)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{cv_text}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    extracted_raw = await _invoke_llm_chain(prompt, parser, {"cv_text": cv_text}, llm_fast)
    extracted_data = CVExtraction.model_validate(extracted_raw)

    _log_progress("extract_cv_node", "Resume extraction completed")
    return {
        "status": "cv_extracted",
        "progress_message": "Resume extraction completed",
        "cv_text": cv_text,
        "personal_info": extracted_data.personal_info.model_dump(),
        "education": [item.model_dump() for item in extracted_data.education],
        "experience": [item.model_dump() for item in extracted_data.experience],
        "extracted_skills": extracted_data.extracted_skills,
        "project_links": _project_links_to_map(extracted_data.project_links),
        "project_total_expected": len(extracted_data.project_links),
    }


async def job_alignment_node(state: InterviewState) -> dict[str, Any]:
    _log_progress("job_alignment_node", f"Aligning profile with {state.get('job_title')}")

    system_prompt = """
    You are an expert IT recruiter.
    Compare the extracted CV skills with the job title and job description.
    If the job description is empty, infer standard requirements for the title.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=JobAlignmentOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "User Skills: {skills}\nJob Title: {title}\nJob Description: {description}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    alignment_raw = await _invoke_llm_chain(
        prompt,
        parser,
        {
            "skills": state.get("extracted_skills", []),
            "title": state.get("job_title", ""),
            "description": state.get("job_description", ""),
        },
        llm_smart,
    )
    alignment = JobAlignmentOutput.model_validate(alignment_raw)

    _log_progress("job_alignment_node", "Alignment completed")
    return {
        "status": "job_aligned",
        "progress_message": "Job alignment completed",
        "job_requirements": alignment.job_requirements,
        "matched_skills": alignment.matched_skills,
        "missing_skills": alignment.missing_skills,
    }


async def validation_node(state: InterviewState) -> dict[str, Any]:
    _log_progress("validation_node", "Validating job alignment")

    system_prompt = """
    You are validating a recruiter analysis.
    Check that the extracted skills and job requirements are logically consistent with the job title.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=ValidationOutput)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Job Title: {title}\nRequirements: {requirements}\nMatched Skills: {matched}\nMissing Skills: {missing}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    validation_raw = await _invoke_llm_chain(
        prompt,
        parser,
        {
            "title": state.get("job_title", ""),
            "requirements": state.get("job_requirements", []),
            "matched": state.get("matched_skills", []),
            "missing": state.get("missing_skills", []),
        },
        llm_smart,
    )
    validation = ValidationOutput.model_validate(validation_raw)

    issues = list(state.get("validation_issues", [])) + validation.issues
    recommendations = list(state.get("validation_recommendations", [])) + validation.recommendations

    if not validation.is_consistent:
        issues.append("Job alignment validation detected inconsistencies.")

    _log_progress("validation_node", "Validation completed")
    return {
        "status": "validated",
        "progress_message": "Validation completed",
        "validation_issues": issues,
        "validation_recommendations": recommendations,
        "normalized_job_title": validation.normalized_job_title or state.get("job_title", ""),
    }


async def market_intelligence_node(state: InterviewState) -> dict[str, Any]:
    _log_progress("market_intelligence_node", "Generating market intelligence queries")

    query_system_prompt = """
    Generate 3 targeted search queries to find the latest interview trends and technical updates.
    Focus on the user's missing skills.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=SearchQueryList)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", query_system_prompt),
            ("human", "Matched: {matched}\nMissing: {missing}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    query_results_raw = await _invoke_llm_chain(
        prompt,
        parser,
        {
            "matched": state.get("matched_skills", []),
            "missing": state.get("missing_skills", []),
        },
        llm_fast,
    )
    query_results = SearchQueryList.model_validate(query_results_raw)

    search_payloads: list[dict[str, Any]] = []
    for query in query_results.queries[:3]:
        try:
            search_result = await _tavily_search(query)
            search_payloads.append({"query": query, "result": search_result})
        except Exception as exc:  # pragma: no cover - defensive logging for runtime integration
            logger.exception("Tavily search failed for query %s", query)
            search_payloads.append({"query": query, "error": str(exc)})

    _log_progress("market_intelligence_node", "Market search completed")
    return {
        "status": "market_researched",
        "progress_message": "Market intelligence completed",
        "search_queries": query_results.queries[:3],
        "search_results": json.dumps(search_payloads, default=str),
        "market_analysis_completed": True,
    }


async def market_summary_node(state: InterviewState) -> dict[str, Any]:
    _log_progress("market_summary_node", "Summarizing market intelligence")

    system_prompt = """
    You are a technical analyst for technical interviews.
    Synthesize the raw search results into a market intelligence report.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=SearchSummary)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Missing Skills: {missing}\n\nRaw Search Data: {data}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    summary_raw = await _invoke_llm_chain(
        prompt,
        parser,
        {
            "missing": state.get("missing_skills", []),
            "data": state.get("search_results", ""),
        },
        llm_smart,
    )
    summary = SearchSummary.model_validate(summary_raw)

    market_summary = {
        "market_trends_2026": summary.market_trends_2026,
        "expected_technical_questions": summary.expected_technical_questions,
        "tech_stack_updates": summary.tech_stack_updates,
    }

    _log_progress("market_summary_node", "Market summarization completed")
    return {
        "status": "market_summarized",
        "progress_message": "Market intelligence summarized",
        "market_summary": market_summary,
    }


async def project_fetch_readme_node(state: InterviewState) -> dict[str, Any]:
    project_name = state.get("project_name", "").strip()
    project_url = state.get("project_url", "").strip()
    _log_progress("project_fetch_readme_node", f"Fetching README for {project_name or project_url}")

    readme_text = ""
    readme_status = "No README found"

    for candidate_url in _github_raw_readme_urls(project_url):
        try:
            readme_text = await _fetch_url(candidate_url)
            readme_status = "README fetched"
            break
        except Exception:
            logger.info("README not available at %s", candidate_url)

    if not readme_text:
        readme_text = state.get("cv_text", "")

    _log_progress("project_fetch_readme_node", f"README status: {readme_status}")
    return {
        "readme_status": readme_status,
        "readme_content": readme_text,
        "project_readmes": {project_name or project_url: readme_text},
    }


async def project_summary_node(state: InterviewState) -> dict[str, Any]:
    project_name = state.get("project_name", "").strip() or state.get("project_url", "").strip()
    _log_progress("project_summary_node", f"Summarizing project {project_name}")

    system_prompt = """
    Analyze this project README and extract technical details.
    Return only JSON matching the provided schema.
    {format_instructions}
    """

    parser = JsonOutputParser(pydantic_object=ProjectDetail)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "Project: {name}\nContent: {content}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    try:
        details_raw = await _invoke_llm_chain(
            prompt,
            parser,
            {
                "name": project_name,
                "content": state.get("readme_content", ""),
            },
            llm_smart,
        )
        details = ProjectDetail.model_validate(details_raw)
        summary = {
            "tech_stack": details.tech_stack,
            "key_features": details.key_features,
            "potential_interview_questions": details.potential_interview_questions,
            "readme_status": state.get("readme_status", ""),
        }
    except Exception as exc:  # pragma: no cover - defensive fallback for runtime integration
        logger.exception("Error summarizing project %s", project_name)
        summary = {
            "tech_stack": [],
            "key_features": [],
            "potential_interview_questions": [],
            "readme_status": state.get("readme_status", "No README found"),
            "error": str(exc),
        }

    _log_progress("project_summary_node", f"Project summary completed for {project_name}")
    return {
        "status": "project_summarized",
        "progress_message": f"Project summary completed for {project_name}",
        "project_summaries": {project_name: summary},
        "project_errors": {project_name: summary["error"]} if "error" in summary else {},
        "project_count_completed": 1,
    }


async def finalize_analysis_node(state: InterviewState) -> dict[str, Any]:
    project_total_expected = int(state.get("project_total_expected", 0) or 0)
    project_completed = int(state.get("project_count_completed", 0) or 0)
    market_ready = bool(state.get("market_analysis_completed", False))

    if not market_ready or (project_total_expected > 0 and project_completed < project_total_expected):
        return {
            "status": "analysis_in_progress",
            "progress_message": "Waiting for all analysis branches to complete",
        }

    final_payload = _build_final_payload(state)
    _log_progress("finalize_analysis_node", "Analysis payload assembled")
    return {
        "status": "analysis_ready",
        "progress_message": "Final analysis payload ready",
        "final_analysis_payload": final_payload.model_dump(),
        "analysis_persisted": False,
    }
