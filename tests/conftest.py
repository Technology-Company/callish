"""Shared fixtures for callish's own tests.

The ``inmemory_adapter`` fixture resets the module-level adapter between
tests so :file:`tests/models.py` can hold a single ``Invoice`` class
(generic views + URL reverse + admin all need stable import targets).
"""

from __future__ import annotations

import pytest

from .models import ADAPTER, Invoice


@pytest.fixture(autouse=True)
def inmemory_adapter():
    """Reset the shared adapter at the top of every test."""
    ADAPTER.reset()
    yield ADAPTER
    ADAPTER.reset()


@pytest.fixture
def invoice_model():
    return Invoice


@pytest.fixture
def seeded(inmemory_adapter):
    """Three invoices: 100/unpaid, 200/paid, 300/unpaid."""
    inmemory_adapter.seed(
        [
            {"id": 1, "number": "INV-001", "amount_cents": 100, "paid": False},
            {"id": 2, "number": "INV-002", "amount_cents": 200, "paid": True},
            {"id": 3, "number": "INV-003", "amount_cents": 300, "paid": False},
        ]
    )
    return inmemory_adapter
