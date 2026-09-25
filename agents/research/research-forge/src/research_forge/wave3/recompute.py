"""Deterministic arithmetic recomputation (RF-W3-A-07)."""

from __future__ import annotations

import ast
import operator
from typing import Any

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _eval_node(node: ast.AST, names: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise ValueError(f"Unknown variable: {node.id}")
        return float(names[node.id])
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.operand, names))  # type: ignore[arg-type]
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        left = _eval_node(node.left, names)
        right = _eval_node(node.right, names)
        return _SAFE_OPS[type(node.op)](left, right)  # type: ignore[operator]
    raise ValueError("Unsupported expression")


def recompute_expression(expression: str, inputs: dict[str, float]) -> dict[str, Any]:
    """Evaluate a closed-form expression with recorded inputs (no model trust)."""
    tree = ast.parse(expression, mode="eval")
    value = _eval_node(tree.body, inputs)
    return {
        "expression": expression,
        "inputs": dict(sorted(inputs.items())),
        "result": value,
        "engine": "sandboxed_ast",
    }
