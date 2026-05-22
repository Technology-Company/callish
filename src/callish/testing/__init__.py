"""Testing utilities for callish.

Importing this module is cheap and does not pull in pytest.
"""

from __future__ import annotations

from .reference_adapter import InMemoryAdapter

__all__ = ["InMemoryAdapter"]
