"""M1 — list / iteration / slice / count / order_by."""

from __future__ import annotations


def test_list_empty(invoice_model):
    assert list(invoice_model.objects.all()) == []


def test_list_single(invoice_model):
    invoice_model.objects.create(number="A", amount_cents=10, paid=False)
    qs = list(invoice_model.objects.all())
    assert len(qs) == 1
    assert qs[0].number == "A"


def test_list_many(seeded, invoice_model):
    qs = list(invoice_model.objects.all())
    assert len(qs) == 3


def test_slice_offset_limit(seeded, invoice_model):
    qs = list(invoice_model.objects.order_by("amount_cents")[1:3])
    assert [o.amount_cents for o in qs] == [200, 300]


def test_order_by_asc(seeded, invoice_model):
    qs = list(invoice_model.objects.order_by("amount_cents"))
    assert [o.amount_cents for o in qs] == [100, 200, 300]


def test_order_by_desc(seeded, invoice_model):
    qs = list(invoice_model.objects.order_by("-amount_cents"))
    assert [o.amount_cents for o in qs] == [300, 200, 100]


def test_count_uses_adapter_count(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.calls["count"] = 0
    assert invoice_model.objects.count() == 3
    assert inmemory_adapter.calls["count"] == 1


def test_count_falls_back_to_len_when_adapter_returns_none(invoice_model, monkeypatch):
    invoice_model.objects.create(number="A", amount_cents=1, paid=False)
    invoice_model.objects.create(number="B", amount_cents=2, paid=False)
    adapter = invoice_model._callish_adapter
    monkeypatch.setattr(adapter, "count", lambda *, filters: None)
    assert invoice_model.objects.count() == 2


def test_iterating_caches_results(seeded, invoice_model, inmemory_adapter):
    qs = invoice_model.objects.all()
    inmemory_adapter.calls["list"] = 0
    list(qs)
    list(qs)
    assert inmemory_adapter.calls["list"] == 1, (
        "Two iterations of the same queryset should hit the adapter once"
    )


def test_iterating_clones_does_refetch(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.calls["list"] = 0
    list(invoice_model.objects.all())
    list(invoice_model.objects.all())  # fresh queryset
    assert inmemory_adapter.calls["list"] == 2
