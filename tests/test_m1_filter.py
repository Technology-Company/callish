"""M1 — filter / exclude lookups."""

from __future__ import annotations


def test_filter_equality(seeded, invoice_model):
    qs = list(invoice_model.objects.filter(paid=True))
    assert [o.number for o in qs] == ["INV-002"]


def test_filter_in_lookup(seeded, invoice_model):
    qs = list(invoice_model.objects.filter(number__in=["INV-001", "INV-003"]))
    assert sorted(o.number for o in qs) == ["INV-001", "INV-003"]


def test_filter_gte_lte(seeded, invoice_model):
    qs = list(invoice_model.objects.filter(amount_cents__gte=200))
    assert sorted(o.amount_cents for o in qs) == [200, 300]

    qs = list(invoice_model.objects.filter(amount_cents__lte=200))
    assert sorted(o.amount_cents for o in qs) == [100, 200]


def test_filter_icontains(seeded, invoice_model):
    qs = list(invoice_model.objects.filter(number__icontains="inv-00"))
    assert len(qs) == 3


def test_filter_chained(seeded, invoice_model):
    qs = list(
        invoice_model.objects.filter(paid=False).filter(amount_cents__gte=200)
    )
    assert [o.amount_cents for o in qs] == [300]


def test_exclude(seeded, invoice_model):
    qs = list(invoice_model.objects.exclude(paid=True))
    assert sorted(o.number for o in qs) == ["INV-001", "INV-003"]
