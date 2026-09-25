"""Tool schemas exposed to model providers.

Names match `config/tools.json`. Only tools in a role's allowlist are advertised, so a
role cannot discover a capability it may not use.
"""
from __future__ import annotations

TOOL_SCHEMAS: dict[str, dict] = {
    "filesystem.read": {"name": "filesystem.read", "description": "Read a file with line numbers. Returns sha256 for later writes.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}},
    "filesystem.list": {"name": "filesystem.list", "description": "List directory entries.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": []}},
    "filesystem.search": {"name": "filesystem.search", "description": "Case-insensitive text search returning file and line citations.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "glob": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
    "filesystem.write": {"name": "filesystem.write", "description": "Write a file inside the approved plan allowlist. expected_sha256 is required when overwriting.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "expected_sha256": {"type": "string"}}, "required": ["path", "content"]}},
    "patch.apply": {"name": "patch.apply", "description": "Replace one unique occurrence of find with replace in an allowlisted file.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "find": {"type": "string"}, "replace": {"type": "string"}, "expected_sha256": {"type": "string"}}, "required": ["path", "find", "replace"]}},
    "repository.status": {"name": "repository.status", "description": "git status --porcelain with branch.",
        "parameters": {"type": "object", "properties": {}, "required": []}},
    "repository.diff": {"name": "repository.diff", "description": "git diff for the working tree or one path.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "staged": {"type": "boolean"}}, "required": []}},
    "repository.history": {"name": "repository.history", "description": "Recent commits, one line each.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []}},
    "shell.readonly": {"name": "shell.readonly", "description": "Run an allowlisted read-only command.",
        "parameters": {"type": "object", "properties": {"argv": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "integer"}}, "required": ["argv"]}},
    "tests.run": {"name": "tests.run", "description": "Run an allowlisted test command and return exit code and output.",
        "parameters": {"type": "object", "properties": {"argv": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "integer"}}, "required": ["argv"]}},
    "web.fetch": {"name": "web.fetch", "description": "Fetch one public URL as text. Read-only.",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}, "max_bytes": {"type": "integer"}}, "required": ["url"]}},
    "web.search": {"name": "web.search", "description": "Search the public web and return titles, URLs, and snippets.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "count": {"type": "integer"}}, "required": ["query"]}},
    "github.repo.metadata": {"name": "github.repo.metadata", "description": "Read-only GitHub repository metadata (owner/repo or url).",
        "parameters": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "url": {"type": "string"}}, "required": []}},
    "github.pull.list": {"name": "github.pull.list", "description": "List pull requests for a GitHub repository (read-only).",
        "parameters": {"type": "object", "properties": {"owner": {"type": "string"}, "repo": {"type": "string"}, "url": {"type": "string"}, "state": {"type": "string"}, "per_page": {"type": "integer"}}, "required": []}},
}

def schemas_for(tool_names):
    return [TOOL_SCHEMAS[name] for name in tool_names if name in TOOL_SCHEMAS]
