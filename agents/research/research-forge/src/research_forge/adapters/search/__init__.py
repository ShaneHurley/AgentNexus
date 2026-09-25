"""Search adapters — mock-first with optional public read-only adapter."""

from research_forge.adapters.search.mock import MockSearchAdapterV1
from research_forge.adapters.search.protocol import NormalizedSearchResult, SearchRequest

__all__ = ["MockSearchAdapterV1", "NormalizedSearchResult", "SearchRequest"]
