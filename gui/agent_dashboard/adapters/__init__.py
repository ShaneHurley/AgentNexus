"""Adapter package — import concrete adapters from here if needed."""

from .daily_coder import DailyCoderAdapter
from .daily_task import DailyTaskAdapter
from .research_forge import ResearchForgeAdapter

ADAPTERS = {
    "daily_coder": DailyCoderAdapter,
    "daily_task": DailyTaskAdapter,
    "research_forge": ResearchForgeAdapter,
}

__all__ = ["ADAPTERS", "DailyCoderAdapter", "DailyTaskAdapter", "ResearchForgeAdapter"]