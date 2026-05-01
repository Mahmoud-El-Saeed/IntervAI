from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.embedder import Embedder
from app.core.analysis_logging import get_analysis_logger

logger = get_analysis_logger(__name__)


def log_progress(node_name: str, message: str, level: int = logging.INFO) -> None:
    """Log node progress with standardized format."""
    logger.log(level, "[%s] %s", node_name, message)


def normalize_github_url(project_url: str) -> tuple[str, str] | None:
    """Extract owner and repo from GitHub URL."""
    normalized = project_url.strip()
    if not normalized:
        return None

    if not normalized.startswith(("http://", "https://")):
        normalized = f"https://{normalized}"

    parsed = urlparse(normalized)
    hostname = (parsed.hostname or "").lower()
    if hostname not in {"github.com", "www.github.com"}:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) < 2:
        return None

    owner = path_parts[0].strip()
    repo = path_parts[1].strip()
    if repo.endswith(".git"):
        repo = repo[:-4]

    if not owner or not repo:
        return None

    return owner, repo


def derive_project_name_from_url(url: str) -> str:
    """Extract a readable name from GitHub URL."""
    print(f"Deriving project name from URL: {url}")
    if not url:
        return "Unknown Project"
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2:
        repo = path_parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return repo.replace("-", " ").replace("_", " ").title()
    return "Unknown Project"


def project_links_to_map(
    project_links: Iterable[dict[str, str]] | Iterable[Any],
) -> dict[str, str]:
    """Convert project link objects to URL mapping with proper naming."""
    project_map: dict[str, str] = {}
    for project in project_links:
        if isinstance(project, dict):
            name = str(project.get("name", "")).strip()
            url = str(project.get("url", "")).strip()
        else:
            name = str(getattr(project, "name", "")).strip()
            url = str(getattr(project, "url", "")).strip()

        if url:
            if not name:
                name = derive_project_name_from_url(url)
            project_map[name] = url

    return project_map


def generate_readme_urls(project_url: str) -> list[str]:
    """Generate potential raw README URLs for a GitHub project."""
    owner_repo = normalize_github_url(project_url)
    if owner_repo is None:
        return []

    owner, repo = owner_repo
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}"
    return [
        f"{raw_base}/main/README.md",
        f"{raw_base}/master/README.md",
    ]


def build_msg(role: str, content: str) -> dict[str, str]:
    """Create a chat message dict."""
    return {"role": role, "content": content}


def normalize_interview_score(score: float | int | None) -> float:
    """Normalize interview scoring to a 100-point scale."""
    if score is None:
        return 0.0

    normalized = float(score)
    if normalized <= 10.0:
        normalized *= 10.0

    return max(0.0, min(100.0, round(normalized, 2)))


def calculate_overall_score(
    matched_skills: list[str],
    missing_skills: list[str],
    job_requirements: list[str] | None = None,
) -> float:
    """Calculate overall match score based on skills analysis.
    
    Score = (matched / total_required) * 100
    - Accounts for all job requirements
    - Penalizes missing skills proportionally
    - Boosts score for extra relevant skills
    """
    total_required = len(matched_skills) + len(missing_skills)
    
    if total_required == 0:
        return 50.0
    
    match_ratio = len(matched_skills) / total_required
    base_score = match_ratio * 100
    
    extra_bonus = min(len(matched_skills) * 0.5, 10.0)
    
    score = base_score + extra_bonus
    return max(0.0, min(100.0, round(score, 1)))


def build_final_verdict(score: float) -> str:
    """Determine final verdict based on overall score."""
    if score >= 80:
        return "Strong match - Candidate is well-qualified"
    elif score >= 60:
        return "Good match - Candidate meets most requirements"
    elif score >= 40:
        return "Partial match - Improve the missing skills"
    else:
        return "Low match - Significant skill gaps to address"
    

def prepare_text_chunks_and_embeddings(text: str, context_prefix: str) -> tuple[list[str], list[list[float]]]:
    """
    Takes text, chunks it, adds a context prefix, and generates embeddings.
    Returns: (list_of_prefixed_chunks, list_of_embeddings)
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    raw_chunks = splitter.split_text(text)
    
    clean_chunks = [chunk.strip() for chunk in raw_chunks if chunk.strip()]
    
    if not clean_chunks:
        return [], []
    
    prefixed_chunks = [f"{context_prefix}: {chunk}" for chunk in clean_chunks]
    
    embedder = Embedder()
    try:
        embeddings = embedder.embed_documents(prefixed_chunks)
        return prefixed_chunks, embeddings
    except Exception as exc:
        raise ValueError(f"Failed to generate embeddings for text chunks: {exc}") from exc