"""Layout and resolution errors."""

from __future__ import annotations


class LayoutError(Exception):
    """Invalid, missing, or conflicting layout signals."""


class RefResolutionError(Exception):
    """Logical reference could not be resolved safely."""
