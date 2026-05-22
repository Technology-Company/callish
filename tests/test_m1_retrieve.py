"""M1 — retrieve and DoesNotExist mapping."""

from __future__ import annotations

import pytest


def test_get_by_pk(seeded, invoice_model):
    obj = invoice_model.objects.get(pk=2)
    assert obj.number == "INV-002"


def test_get_by_explicit_pk_field(seeded, invoice_model):
    obj = invoice_model.objects.get(id=3)
    assert obj.number == "INV-003"


def test_get_missing_raises_does_not_exist(invoice_model):
    with pytest.raises(invoice_model.DoesNotExist):
        invoice_model.objects.get(pk=42)


def test_get_uses_adapter_retrieve_for_pk(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.calls["retrieve"] = 0
    invoice_model.objects.get(pk=1)
    assert inmemory_adapter.calls["retrieve"] == 1


def test_get_by_non_pk_falls_back_to_list(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.calls["list"] = 0
    obj = invoice_model.objects.get(number="INV-002")
    assert obj.pk == 2
    assert inmemory_adapter.calls["list"] == 1


def test_refresh_from_db(invoice_model):
    obj = invoice_model.objects.create(number="A", amount_cents=10, paid=False)
    # Mutate "upstream" directly.
    invoice_model._callish_adapter._store[obj.pk]["paid"] = True
    obj.refresh_from_db()
    assert obj.paid is True
