"""M2 — create."""

from __future__ import annotations


def test_create_assigns_pk(invoice_model):
    obj = invoice_model(number="NEW", amount_cents=100, paid=False)
    assert obj.pk is None
    obj.save()
    assert obj.pk is not None


def test_create_via_manager_shortcut(invoice_model):
    obj = invoice_model.objects.create(number="VIA-MGR", amount_cents=5, paid=True)
    assert obj.pk is not None
    assert obj.paid is True


def test_create_round_trip(invoice_model):
    obj = invoice_model.objects.create(number="RT", amount_cents=42, paid=False)
    again = invoice_model.objects.get(pk=obj.pk)
    assert again.number == "RT"


def test_create_with_partial_fields(invoice_model):
    obj = invoice_model(number="MIN")
    obj.save()
    assert obj.pk is not None
    assert obj.number == "MIN"
