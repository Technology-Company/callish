"""Function-based Django views using APIModel directly.

Complements ``test_generic_views.py`` (which covers ``ListView``/``DetailView``/
etc.). These tests exercise the case where a user writes plain ``def view(...)``
code and calls ``Invoice.objects.filter / .get / .create / .save`` inline —
the lowest-ceremony Django integration path.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def test_summary_uses_filter_and_iteration(seeded, client, inmemory_adapter):
    """View calls ``Invoice.objects.filter(paid=False)`` and iterates the queryset."""
    response = client.get("/api/invoices/summary/")
    assert response.status_code == 200
    body = response.json()
    # Seeded fixture has two unpaid invoices: 100 and 300.
    assert body == {"unpaid_count": 2, "total_cents": 400}
    # filter() + count() + iteration should both have hit the adapter.
    assert inmemory_adapter.calls["list"] >= 1


def test_search_passes_querystring_into_filter(seeded, client):
    response = client.get("/api/invoices/search/?q=002")
    assert response.status_code == 200
    assert response.json() == {"numbers": ["INV-002"]}


def test_search_with_no_query_returns_all(seeded, client):
    response = client.get("/api/invoices/search/")
    assert response.status_code == 200
    # Ordered by amount_cents ascending.
    assert response.json() == {"numbers": ["INV-001", "INV-002", "INV-003"]}


def test_mark_paid_does_get_then_save(seeded, client, inmemory_adapter):
    response = client.post("/api/invoices/1/pay/")
    assert response.status_code == 200
    assert response.json() == {"pk": 1, "paid": True}
    # The view does Invoice.objects.get(pk=1) → retrieve(); then save() → update().
    assert inmemory_adapter.calls["retrieve"] == 1
    assert inmemory_adapter.calls["update"] == 1
    assert inmemory_adapter._store[1]["paid"] is True


def test_mark_paid_returns_404_when_missing(client):
    """View's ``Invoice.DoesNotExist`` catch is the APIModel mapping in action."""
    response = client.post("/api/invoices/9999/pay/")
    assert response.status_code == 404


def test_create_json_round_trips_through_adapter(client, inmemory_adapter):
    payload = {"number": "JSON-1", "amount_cents": 1234, "paid": False}
    response = client.post(
        "/api/invoices/",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body["number"] == "JSON-1"
    assert body["amount_cents"] == 1234
    assert body["pk"] is not None
    assert inmemory_adapter.calls["create"] == 1


def test_get_only_endpoints_reject_post(client):
    """``@require_http_methods(["POST"])`` plays nicely with APIModel views."""
    response = client.get("/api/invoices/1/pay/")
    assert response.status_code == 405