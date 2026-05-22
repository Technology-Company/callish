"""APIQuerySet surface — chaining, slicing, caching, terminal helpers."""

from __future__ import annotations

import pytest

from callish.queryset import APIQuerySet


def test_filter_returns_new_queryset(invoice_model):
    qs = invoice_model.objects.all()
    filtered = qs.filter(paid=True)
    assert qs is not filtered
    assert isinstance(filtered, APIQuerySet)


def test_chained_filters_accumulate(invoice_model):
    qs = invoice_model.objects.filter(paid=True).filter(amount_cents=100)
    assert qs._filters == {"paid": True, "amount_cents": 100}


def test_order_by_accumulates(invoice_model):
    qs = invoice_model.objects.order_by("number", "-amount_cents")
    assert qs._ordering == ("number", "-amount_cents")


def test_negative_indexing_rejected(seeded, invoice_model):
    with pytest.raises(ValueError):
        invoice_model.objects.all()[-1]


def test_slice_step_rejected(seeded, invoice_model):
    with pytest.raises(ValueError):
        invoice_model.objects.all()[0:5:2]


def test_first_returns_none_when_empty(invoice_model):
    assert invoice_model.objects.all().first() is None


def test_first_returns_first(seeded, invoice_model):
    obj = invoice_model.objects.order_by("amount_cents").first()
    assert obj.amount_cents == 100


def test_last_returns_last(seeded, invoice_model):
    obj = invoice_model.objects.order_by("amount_cents").last()
    assert obj.amount_cents == 300


def test_exists_true_false(seeded, invoice_model):
    assert invoice_model.objects.all().exists() is True
    assert invoice_model.objects.filter(amount_cents=999_999).exists() is False


def test_none_returns_empty(invoice_model):
    assert list(invoice_model.objects.none()) == []


def test_get_multiple_returns_raises(seeded, invoice_model):
    with pytest.raises(Exception) as exc_info:  # MultipleObjectsReturned
        invoice_model.objects.get(paid=False)
    assert "more than one" in str(exc_info.value).lower()


def test_slice_pushed_to_adapter(invoice_model, inmemory_adapter):
    for i in range(10):
        invoice_model.objects.create(number=f"INV-{i}", amount_cents=i, paid=False)
    inmemory_adapter.calls["list"] = 0
    qs = invoice_model.objects.all()[2:5]
    # Slicing alone should not hit the adapter; only iteration does.
    assert inmemory_adapter.calls["list"] == 0
    list(qs)
    assert inmemory_adapter.calls["list"] == 1
