"""M2 — delete."""

from __future__ import annotations

import pytest

from callish.exceptions import NotFound


def test_delete_removes_record(invoice_model):
    obj = invoice_model.objects.create(number="X", amount_cents=0, paid=False)
    pk = obj.pk
    obj.delete()
    with pytest.raises(invoice_model.DoesNotExist):
        invoice_model.objects.get(pk=pk)


def test_delete_clears_pk(invoice_model):
    obj = invoice_model.objects.create(number="X", amount_cents=0, paid=False)
    obj.delete()
    assert obj.pk is None


def test_delete_without_pk_raises(invoice_model):
    obj = invoice_model(number="UNSAVED")
    with pytest.raises(ValueError):
        obj.delete()


def test_delete_missing_pk_raises_notfound(invoice_model):
    obj = invoice_model(number="GHOST")
    obj.pk = 999
    with pytest.raises(NotFound):
        obj.delete()
