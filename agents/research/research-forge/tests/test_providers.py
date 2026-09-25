from __future__ import annotations

from research_forge.providers.mock_model import MockModel
from research_forge.providers.mock_reader import MockReaderAdapter
from research_forge.providers.mock_search import MockSearchAdapter


def test_mock_model_deterministic() -> None:
    m = MockModel()
    a = m.complete("hello", task_id="t1")
    b = m.complete("hello", task_id="t1")
    assert a == b


def test_mock_search_pagination() -> None:
    s = MockSearchAdapter()
    p1 = s.search("q", page_size=1, cursor=0)
    p2 = s.search("q", page_size=1, cursor=1)
    assert p1["results"][0]["url"] != p2["results"][0]["url"]
    assert p1["next_cursor"] == 1


def test_mock_reader_access_levels() -> None:
    r = MockReaderAdapter()
    full = r.read("https://example.org/a")
    abstract = r.read("https://example.org/b")
    assert full["access_level"] == "full"
    assert abstract["access_level"] == "abstract"
