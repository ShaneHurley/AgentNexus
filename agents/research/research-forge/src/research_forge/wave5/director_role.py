"""Principal Research Director role policy (RF-W5-B-01)."""

from __future__ import annotations

from research_forge.wave5.types import DIRECTOR_ALLOWED_TOOLS, DIRECTOR_ROLE_ID


class DirectorPolicyError(PermissionError):
    pass


class PrincipalResearchDirector:
    role_id = DIRECTOR_ROLE_ID
    allowed_tools = DIRECTOR_ALLOWED_TOOLS
    forbidden_tools = ("search", "reader", "shell", "write", "public_search", "web_read")

    def assert_tool(self, tool_name: str) -> None:
        if tool_name in self.forbidden_tools:
            raise DirectorPolicyError(f"Director cannot use tool {tool_name}")
        if tool_name not in self.allowed_tools:
            raise DirectorPolicyError(f"Tool {tool_name} not in synthesis allowlist")

    def manifest(self) -> dict[str, str | list[str]]:
        return {
            "role_id": self.role_id,
            "tools": list(self.allowed_tools),
            "mode": "structured_synthesis_only",
        }
