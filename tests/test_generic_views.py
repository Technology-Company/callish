"""Generic class-based views work against APIModel."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.fixture
def client():
    return Client()


def test_list_view_renders_seeded(seeded, client):
    response = client.get("/invoices/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "INV-001" in body
    assert "INV-002" in body
    assert "INV-003" in body


def test_list_view_empty(client):
    response = client.get("/invoices/")
    assert response.status_code == 200
    assert "no invoices" in response.content.decode()


def test_detail_view_renders(seeded, client):
    response = client.get("/invoices/2/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "INV-002" in body
    assert "200" in body


def test_detail_view_404_on_missing(client):
    response = client.get("/invoices/9999/")
    assert response.status_code == 404


def test_create_view_get_renders_form(client):
    response = client.get("/invoices/new/")
    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="number"' in body


def test_create_view_post_persists_via_adapter(client, inmemory_adapter):
    response = client.post(
        "/invoices/new/",
        data={"number": "CV-1", "amount_cents": "999", "paid": ""},
    )
    assert response.status_code == 302
    assert inmemory_adapter.calls["create"] == 1


def test_update_view_get_prepopulates(seeded, client):
    response = client.get("/invoices/1/edit/")
    assert response.status_code == 200
    body = response.content.decode()
    assert 'value="INV-001"' in body


def test_update_view_post_updates(seeded, client, inmemory_adapter):
    response = client.post(
        "/invoices/1/edit/",
        data={"number": "INV-001-EDITED", "amount_cents": "100", "paid": ""},
    )
    assert response.status_code == 302
    assert inmemory_adapter.calls["update"] == 1
    assert inmemory_adapter._store[1]["number"] == "INV-001-EDITED"


def test_delete_view_get_confirms(seeded, client):
    response = client.get("/invoices/3/delete/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "delete" in body.lower()


def test_delete_view_post_deletes(seeded, client, inmemory_adapter):
    response = client.post("/invoices/3/delete/")
    assert response.status_code == 302
    assert inmemory_adapter.calls["delete"] == 1
    assert 3 not in inmemory_adapter._store
