"""Validate prospective pull requests against their task and parent epic."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LAST_LEGACY_PR = 86
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
FIELDS = {
    "task": re.compile(r"^Task:\s*#([1-9]\d*)\s*$", re.MULTILINE),
    "epic": re.compile(r"^Epic:\s*#([1-9]\d*)\s*$", re.MULTILINE),
}
PARENT = re.compile(r"^Parent:\s*#([1-9]\d*)\s*$", re.MULTILINE)


class LinkError(ValueError):
    """A PR lacks a verified task and parent epic."""


def _one(pattern: re.Pattern[str], body: str, label: str) -> int:
    matches = pattern.findall(body)
    if len(matches) != 1:
        raise LinkError(f"Provide exactly one {label}: #<issue number> line")
    return int(matches[0])


def validate(event: dict, load_issue) -> dict:
    pr = event.get("pull_request")
    repo = event.get("repository")
    if not isinstance(pr, dict) or not isinstance(repo, dict):
        raise LinkError("GitHub pull request event is required")
    number = pr.get("number")
    if type(number) is not int or number < 1:
        raise LinkError("Pull request number is invalid")
    if number <= LAST_LEGACY_PR:
        return {"status": "legacy", "pr": number}
    name = repo.get("full_name")
    if not isinstance(name, str) or not REPOSITORY.fullmatch(name):
        raise LinkError("Repository identity is invalid")
    body = pr.get("body")
    if not isinstance(body, str):
        raise LinkError("Pull request body is required")
    task = _one(FIELDS["task"], body, "Task")
    epic = _one(FIELDS["epic"], body, "Epic")
    if task == epic:
        raise LinkError("Task and epic must be different issues")
    task_issue = load_issue(task)
    epic_issue = load_issue(epic)
    if not isinstance(task_issue, dict) or "pull_request" in task_issue:
        raise LinkError("Task reference must resolve to an issue")
    if not isinstance(epic_issue, dict) or "pull_request" in epic_issue:
        raise LinkError("Epic reference must resolve to an issue")
    task_body = task_issue.get("body")
    if not isinstance(task_body, str):
        raise LinkError("Task issue must state its parent epic")
    parent = _one(PARENT, task_body, "Parent")
    if parent != epic:
        raise LinkError("Task issue Parent does not match the PR epic")
    return {"status": "verified", "pr": number, "task": task, "epic": epic}


def github_issue_loader(repository: str, token: str):
    if not REPOSITORY.fullmatch(repository):
        raise LinkError("Repository identity is invalid")
    if not token:
        raise LinkError("GITHUB_TOKEN is required for issue verification")

    def load(number: int) -> dict:
        if type(number) is not int or number < 1:
            raise LinkError("Issue number is invalid")
        request = Request(
            f"https://api.github.com/repos/{repository}/issues/{number}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise LinkError(f"Could not verify issue #{number} through GitHub") from exc

    return load


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("GITHUB_EVENT_PATH is required", file=sys.stderr)
        return 1
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
        repository = event.get("repository", {}).get("full_name", "")
        number = event.get("pull_request", {}).get("number")
        if type(number) is int and number <= LAST_LEGACY_PR:
            result = validate(event, lambda _: None)
        else:
            result = validate(event, github_issue_loader(repository, os.environ.get("GITHUB_TOKEN", "")))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        print(f"PR issue-link check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
