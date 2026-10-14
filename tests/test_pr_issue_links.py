"""Meaningful checks for prospective PR task and epic links."""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools/check_pr_issue_links.py"
spec = importlib.util.spec_from_file_location("check_pr_issue_links", SCRIPT)
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


def event(number=87, body="Task: #34\nEpic: #26\n"):
    return {
        "pull_request": {"number": number, "body": body},
        "repository": {"full_name": "ShaneHurley/AgentNexus"},
    }


def issues(parent=26):
    return {34: {"body": f"Parent: #{parent}\n"}, 26: {"body": "## Epic\n"}}


def test_valid_link_checks_task_parent_relationship():
    records = issues()
    assert links.validate(event(), records.__getitem__) == {
        "status": "verified", "pr": 87, "task": 34, "epic": 26
    }


def test_existing_pr_is_grandfathered_without_network_or_body():
    old = event(86, None)
    assert links.validate(old, lambda _: pytest.fail("legacy PR should not fetch issues")) == {
        "status": "legacy", "pr": 86
    }


@pytest.mark.parametrize("body", [
    "", "Task: #34\n", "Epic: #26\n", "Task: #34\nTask: #35\nEpic: #26\n",
    "Task: #34\nEpic: #26\nEpic: #27\n", "Task: #26\nEpic: #26\n",
    "Task: https://github.com/ShaneHurley/AgentNexus/issues/34\nEpic: #26\n",
])
def test_missing_duplicate_or_ambiguous_links_fail(body):
    with pytest.raises(links.LinkError):
        links.validate(event(body=body), issues().__getitem__)


@pytest.mark.parametrize("records", [
    {34: {"body": "Parent: #27\n"}, 26: {"body": "## Epic\n"}},
    {34: {"body": "No parent"}, 26: {"body": "## Epic\n"}},
    {34: {"body": "Parent: #26\nParent: #26\n"}, 26: {"body": "## Epic\n"}},
    {34: {"body": "Parent: #26\n", "pull_request": {}}, 26: {"body": "## Epic\n"}},
    {34: {"body": "Parent: #26\n"}, 26: {"body": "", "pull_request": {}}},
])
def test_wrong_parent_or_pull_request_reference_fails(records):
    with pytest.raises(links.LinkError):
        links.validate(event(), records.__getitem__)


def test_repository_identity_is_checked():
    item = event()
    item["repository"]["full_name"] = "ShaneHurley/AgentNexus/other"
    with pytest.raises(links.LinkError):
        links.validate(item, issues().__getitem__)


def test_missing_issue_fails():
    with pytest.raises(KeyError):
        links.validate(event(), {}.__getitem__)


def test_network_loader_requires_token():
    with pytest.raises(links.LinkError, match="GITHUB_TOKEN"):
        links.github_issue_loader("ShaneHurley/AgentNexus", "")
