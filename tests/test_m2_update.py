"""M2 — update."""

from __future__ import annotations

import pytest

from callish.exceptions import NotFound


def test_update_round_trip(invoice_model):
    obj = invoice_model.objects.create(number="OG", amount_cents=100, paid=False)
    obj.paid = True
    obj.save()
    assert invoice_model.objects.get(pk=obj.pk).paid is True


def test_update_missing_pk_raises_notfound(invoice_model):
    obj = invoice_model(number="GHOST", amount_cents=0, paid=False)
    obj.pk = 999
    with pytest.raises(NotFound):
        obj.save()


def test_update_calls_adapter_update_not_create(invoice_model, inmemory_adapter):
    obj = invoice_model.objects.create(number="OG", amount_cents=100, paid=False)
    inmemory_adapter.calls["update"] = 0
    inmemory_adapter.calls["create"] = 0
    obj.paid = True
    obj.save()
    assert inmemory_adapter.calls["update"] == 1
    assert inmemory_adapter.calls["create"] == 0
