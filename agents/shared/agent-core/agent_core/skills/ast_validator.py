"""AST Validator Skill.

Performs static syntax and structure validation on Python code using Python's
built-in ast module without executing the code.
"""

from __future__ import annotations

import ast
from typing import Any


def validate_python_code(code: str) -> dict[str, Any]:
    """Validate Python source code syntax and extract structural AST summary.

    Args:
        code: Python source code as a string.

    Returns:
        dict with keys:
            - valid: bool, True if parsing succeeded without SyntaxError.
            - syntax_error: str | None, description of syntax error if invalid.
            - ast_summary: dict containing top-level functions, classes, imports,
              total node count, docstring, and async usage.
    """
    if not isinstance(code, str):
        return {
            "valid": False,
            "syntax_error": f"Expected string code input, got {type(code).__name__}",
            "ast_summary": {},
        }

    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        lineno = exc.lineno or 1
        offset = exc.offset or 0
        msg = exc.msg or "Syntax error"
        return {
            "valid": False,
            "syntax_error": f"Line {lineno}:{offset}: {msg}",
            "ast_summary": {},
        }
    except Exception as exc:  # Catch other unexpected parse exceptions
        return {
            "valid": False,
            "syntax_error": f"Parse error: {type(exc).__name__}: {exc}",
            "ast_summary": {},
        }

    # Extract high-level structural summary
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    has_async = False
    total_nodes = 0

    for node in ast.walk(tree):
        total_nodes += 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if isinstance(node, ast.AsyncFunctionDef):
                has_async = True
            # Check if top-level or method
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                imports.append(f"{mod}.{alias.name}" if mod else alias.name)
        elif isinstance(node, (ast.AsyncFor, ast.AsyncWith, ast.Await)):
            has_async = True

    module_doc = ast.get_docstring(tree)

    summary = {
        "total_nodes": total_nodes,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "has_async": has_async,
        "docstring": module_doc,
    }

    return {
        "valid": True,
        "syntax_error": None,
        "ast_summary": summary,
    }
