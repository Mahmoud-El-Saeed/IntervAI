from __future__ import annotations

import asyncio
import os
from typing import Any
from uuid import UUID

import httpx
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain_tavily import TavilySearch
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.database import SessionLocal
from app.core.config import get_settings
from app.core.analysis_logging import get_analysis_logger
from app.db.document_embedding_crud import create_document_embeddings
from .constants import (
    LLM_DEFAULT_TEMPERATURE,
    LLM_FAST_MODEL,
    LLM_SMART_MODEL,
    MAX_SEARCH_RESULTS,
    HTTP_TIMEOUT,
    RETRY_MAX_ATTEMPTS,
    RETRY_MIN_WAIT,
    RETRY_MAX_WAIT,
    RETRY_WAIT_MULTIPLIER,
    LLM_TEMP_EXTRACTION,
    LLM_TEMP_ALIGNMENT,
    LLM_TEMP_VALIDATION,
    LLM_TEMP_QUERY,
    LLM_TEMP_SUMMARY,
    LLM_TEMP_PROJECT,
    LLM_TEMP_STRATEGY,
    LLM_TEMP_QUESTION,
    LLM_TEMP_ANALYSIS,
    LLM_TEMP_HINT,
    LLM_TEMP_EVALUATION,
    LLM_TEMP_REPORT,
)
from .exceptions import LLMError, SearchError
from .prompts import SYSTEM_JSON_REPAIR

settings = get_settings()
logger = get_analysis_logger(__name__)

from dotenv import load_dotenv
load_dotenv('/home/el-saeed/IntervAI/backend/.env')

class LLMService:
    """Service for LLM operations with dependency injection."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = LLM_SMART_MODEL,
        temperature: float = LLM_DEFAULT_TEMPERATURE,
    ):
        self._api_key = api_key or settings.GROQ_API_KEY
        self._model = model
        self._temperature = temperature
        self._client: ChatGroq | None = None

    @property
    def client(self) -> ChatGroq:
        if not self._api_key:
            raise LLMError("GROQ_API_KEY is required")
        if self._client is None:
            self._client = ChatGroq(
                model=self._model,
                temperature=self._temperature,
                api_key=self._api_key,
                
            )
        return self._client

    def update_model(self, model: str) -> None:
        self._model = model
        self._client = None

    def update_temperature(self, temperature: float) -> None:
        self._temperature = temperature
        self._client = None


class SearchService:
    """Service for search operations."""

    def __init__(self, api_key: str | None = None, max_results: int = MAX_SEARCH_RESULTS):
        self._api_key = api_key or settings.TAVILY_API_KEY
        self._max_results = max_results
        self._client: TavilySearch | None = None

    @property
    def client(self) -> TavilySearch:
        if not self._api_key:
            raise SearchError("TAVILY_API_KEY is required")
        if self._client is None:
            self._client = TavilySearch(
                max_results=self._max_results,
                tavily_api_key=self._api_key,
            )
        return self._client


_llm_smart_service: LLMService | None = None
_llm_fast_service: LLMService | None = None
_llm_extraction_service: LLMService | None = None
_llm_alignment_service: LLMService | None = None
_llm_validation_service: LLMService | None = None
_llm_query_service: LLMService | None = None
_llm_summary_service: LLMService | None = None
_llm_project_service: LLMService | None = None
_llm_strategy_service: LLMService | None = None
_llm_question_service: LLMService | None = None
_llm_analysis_service: LLMService | None = None
_llm_hint_service: LLMService | None = None
_llm_evaluation_service: LLMService | None = None
_llm_report_service: LLMService | None = None
_search_service: SearchService | None = None


def get_llm_smart_service() -> LLMService:
    global _llm_smart_service
    if _llm_smart_service is None:
        _llm_smart_service = LLMService(model=LLM_SMART_MODEL)
    return _llm_smart_service


def get_llm_fast_service() -> LLMService:
    global _llm_fast_service
    if _llm_fast_service is None:
        _llm_fast_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_DEFAULT_TEMPERATURE)
    return _llm_fast_service


def get_extraction_service() -> LLMService:
    global _llm_extraction_service
    if _llm_extraction_service is None:
        _llm_extraction_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_EXTRACTION)
    return _llm_extraction_service

def get_summary_chat_service() -> LLMService:
    global _llm_summary_service
    if _llm_summary_service is None:
        _llm_summary_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_SUMMARY)
    return _llm_summary_service


def get_alignment_service() -> LLMService:
    global _llm_alignment_service
    if _llm_alignment_service is None:
        _llm_alignment_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_ALIGNMENT)
    return _llm_alignment_service


def get_validation_service() -> LLMService:
    global _llm_validation_service
    if _llm_validation_service is None:
        _llm_validation_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_VALIDATION)
    return _llm_validation_service


def get_query_service() -> LLMService:
    global _llm_query_service
    if _llm_query_service is None:
        _llm_query_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_QUERY)
    return _llm_query_service


def get_summary_service() -> LLMService:
    global _llm_summary_service
    if _llm_summary_service is None:
        _llm_summary_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_SUMMARY)
    return _llm_summary_service


def get_project_service() -> LLMService:
    global _llm_project_service
    if _llm_project_service is None:
        _llm_project_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_PROJECT)
    return _llm_project_service


def get_strategy_service() -> LLMService:
    global _llm_strategy_service
    if _llm_strategy_service is None:
        _llm_strategy_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_STRATEGY)
    return _llm_strategy_service


def get_question_service() -> LLMService:
    global _llm_question_service
    if _llm_question_service is None:
        _llm_question_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_QUESTION)
    return _llm_question_service


def get_analysis_service() -> LLMService:
    global _llm_analysis_service
    if _llm_analysis_service is None:
        _llm_analysis_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_ANALYSIS)
    return _llm_analysis_service


def get_hint_service() -> LLMService:
    global _llm_hint_service
    if _llm_hint_service is None:
        _llm_hint_service = LLMService(model=LLM_FAST_MODEL, temperature=LLM_TEMP_HINT)
    return _llm_hint_service


def get_evaluation_service() -> LLMService:
    global _llm_evaluation_service
    if _llm_evaluation_service is None:
        _llm_evaluation_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_EVALUATION)
    return _llm_evaluation_service


def get_report_service() -> LLMService:
    global _llm_report_service
    if _llm_report_service is None:
        _llm_report_service = LLMService(model=LLM_SMART_MODEL, temperature=LLM_TEMP_REPORT)
    return _llm_report_service


def get_search_service() -> SearchService:
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service


async def invoke_llm_json(
    prompt: ChatPromptTemplate,
    parser: JsonOutputParser,
    payload: dict[str, Any],
    service: LLMService,
) -> dict[str, Any]:
    """Invoke LLM with JSON output using provided service."""
    chain = prompt | service.client.bind(response_format={"type": "json_object"}) | parser
    return await chain.ainvoke(payload)


@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def invoke_llm_chain(
    prompt: ChatPromptTemplate,
    parser: JsonOutputParser,
    payload: dict[str, Any],
    service: LLMService,
) -> dict[str, Any]:
    """Invoke LLM with retry logic."""
    try:
        return await invoke_llm_json(prompt, parser, payload, service)
    except Exception as e:
        logger.error(f"LLM invocation failed: {e}")
        raise LLMError(f"LLM invocation failed: {e}") from e


@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def search_query(query: str, service: SearchService) -> Any:
    """Execute search query with retry logic."""
    try:
        return await asyncio.to_thread(service.client.invoke, {"query": query})
    except Exception as e:
        logger.error(f"Search failed for query '{query}': {e}")
        raise SearchError(f"Search failed: {e}") from e


@retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT),
    retry=retry_if_exception_type((httpx.HTTPError, ValueError, RuntimeError)),
    reraise=True,
)
async def fetch_url(url: str) -> str:
    """Fetch URL content with retry logic."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=HTTP_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching {url}: {e}")
        raise SearchError(f"HTTP error: {e}") from e
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        raise SearchError(f"Fetch error: {e}") from e


async def safe_parse_json(
    text: str,
    schema: Any,
    service: LLMService,
    max_attempts: int = 3,
) -> Any:
    """Parse JSON with repair attempts."""
    from pydantic import ValidationError

    parser = JsonOutputParser(pydantic_object=schema)
    parse_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_JSON_REPAIR),
            ("human", "{repair_request}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    base_prompt = (
        "Return valid JSON only. No markdown, no prose. "
        "Match the target schema exactly.\n\n"
        f"Target schema: {schema.model_json_schema()}\n\n"
        f"Input to parse:\n{text}"
    )

    for attempt in range(max_attempts):
        try:
            repaired_raw = await parse_prompt.ainvoke(
                {"repair_request": base_prompt},
                config={"configurable": {"model": service.client}},
            )
            parser.parse(repaired_raw)
            return schema.model_validate_json(repaired_raw.content)
        except ValidationError as e:
            base_prompt += f"\n\nAttempt {attempt + 1} validation error: {str(e)}"
            continue

    raise LLMError(f"Could not parse JSON into {schema.__name__} after {max_attempts} attempts")

def save_project_embeddings(resume_id_str: str, chunks: list[str], embeddings: list[list[float]]) -> None:
    """
    Synchronously save project embeddings to the database.
    """

    
    if not chunks or not embeddings:
        return

    if len(chunks) != len(embeddings):
        raise ValueError("Chunks count does not match embeddings count.")

    db = SessionLocal()
    try:
        create_document_embeddings(
            db=db,
            resume_id=UUID(resume_id_str),
            chunks=chunks,
            embeddings=embeddings
        )
    except Exception as e:
        db.rollback()
        raise RuntimeError(f"Database error saving embeddings: {e}") from e
    finally:
        db.close()