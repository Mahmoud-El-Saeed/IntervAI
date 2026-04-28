class AIError(Exception):
    """Base exception for AI module."""


class LLMError(AIError):
    """Raised when LLM invocation fails."""


class SearchError(AIError):
    """Raised when search operation fails."""


class CVExtractionError(AIError):
    """Raised when CV extraction fails."""


class JobAlignmentError(AIError):
    """Raised when job alignment fails."""


class ValidationError(AIError):
    """Raised when validation fails."""


class MarketAnalysisError(AIError):
    """Raised when market analysis fails."""


class ProjectFetchError(AIError):
    """Raised when project README fetch fails."""


class InterviewError(AIError):
    """Raised when interview flow fails."""


class StateError(AIError):
    """Raised when state operation fails."""