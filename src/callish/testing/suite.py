"""Conformance suite — milestone-organised tests that exercise the adapter contract.

Run via:

    pytest --pyargs callish.testing.suite

Downstream users define a ``conform_adapter`` fixture (in their conftest)
returning a fresh instance of their adapter. The plugin auto-injects
``conform_model`` (a canonical Invoice-shaped APIModel pointed at that
adapter) so tests look the same across all adapters.

Each test is tagged with ``@pytest.mark.callish_milestone("m1" | "m2" | "m3")``
so users adopting incrementally can skip later milestones with
``--callish-skip-m3``.
"""

from __future__ import annotations

import pytest

from ..exceptions import (
    AdapterValidationError,
    NotFound,
    RateLimited,
    Unauthorized,
    Upstream5xx,
)

__all__ = []  # noqa: RUF022 — file is collected by pytest, not imported as API


# ---------------------------------------------------------------------------
# M1 — Read path
# ---------------------------------------------------------------------------


@pytest.mark.callish_milestone("m1")
def test_m1_list_empty(conform_model):
    qs = list(conform_model.objects.all())
    assert qs == [], "Empty store should yield an empty list"


@pytest.mark.callish_milestone("m1")
def test_m1_list_single(conform_model):
    conform_model.objects.create(number="INV-1", amount_cents=100, paid=False)
    qs = list(conform_model.objects.all())
    assert len(qs) == 1
    assert qs[0].number == "INV-1"


@pytest.mark.callish_milestone("m1")
def test_m1_list_many(conform_model):
    for i in range(5):
        conform_model.objects.create(
            number=f"INV-{i}", amount_cents=i * 100, paid=False
        )
    qs = list(conform_model.objects.all())
    assert len(qs) == 5


@pytest.mark.callish_milestone("m1")
def test_m1_list_offset_limit(conform_model):
    for i in range(10):
        conform_model.objects.create(
            number=f"INV-{i}", amount_cents=i * 100, paid=False
        )
    qs = list(conform_model.objects.all()[2:5])
    assert len(qs) == 3
    # Order isn't guaranteed without order_by, but slicing should be honoured.


@pytest.mark.callish_milestone("m1")
def test_m1_list_ordering(conform_model):
    for amount in [300, 100, 200]:
        conform_model.objects.create(
            number=f"INV-{amount}", amount_cents=amount, paid=False
        )
    qs = list(conform_model.objects.order_by("amount_cents"))
    assert [o.amount_cents for o in qs] == [100, 200, 300]

    qs = list(conform_model.objects.order_by("-amount_cents"))
    assert [o.amount_cents for o in qs] == [300, 200, 100]


@pytest.mark.callish_milestone("m1")
def test_m1_retrieve_by_pk(conform_model):
    created = conform_model.objects.create(
        number="INV-X", amount_cents=42, paid=False
    )
    got = conform_model.objects.get(pk=created.pk)
    assert got.number == "INV-X"


@pytest.mark.callish_milestone("m1")
def test_m1_retrieve_missing(conform_model):
    with pytest.raises(conform_model.DoesNotExist):
        conform_model.objects.get(pk=999_999)


@pytest.mark.callish_milestone("m1")
def test_m1_filter_equality(conform_model):
    conform_model.objects.create(number="A", amount_cents=10, paid=True)
    conform_model.objects.create(number="B", amount_cents=20, paid=False)
    qs = list(conform_model.objects.filter(paid=True))
    assert len(qs) == 1
    assert qs[0].number == "A"


@pytest.mark.callish_milestone("m1")
def test_m1_filter_in_lookup(conform_model):
    adapter = conform_model._callish_adapter
    if "in" not in getattr(adapter, "supported_lookups", ()):
        pytest.skip("adapter does not claim 'in' lookup support")
    conform_model.objects.create(number="A", amount_cents=1, paid=False)
    conform_model.objects.create(number="B", amount_cents=2, paid=False)
    conform_model.objects.create(number="C", amount_cents=3, paid=False)
    qs = list(conform_model.objects.filter(number__in=["A", "C"]))
    assert sorted(o.number for o in qs) == ["A", "C"]


@pytest.mark.callish_milestone("m1")
def test_m1_filter_gte_lookup(conform_model):
    adapter = conform_model._callish_adapter
    if "gte" not in getattr(adapter, "supported_lookups", ()):
        pytest.skip("adapter does not claim 'gte' lookup support")
    for i in range(5):
        conform_model.objects.create(
            number=f"INV-{i}", amount_cents=i * 100, paid=False
        )
    qs = list(conform_model.objects.filter(amount_cents__gte=200))
    assert all(o.amount_cents >= 200 for o in qs)
    assert len(qs) == 3


@pytest.mark.callish_milestone("m1")
def test_m1_count(conform_model):
    for i in range(7):
        conform_model.objects.create(
            number=f"INV-{i}", amount_cents=i * 10, paid=(i % 2 == 0)
        )
    assert conform_model.objects.count() == 7
    assert conform_model.objects.filter(paid=True).count() == 4


# ---------------------------------------------------------------------------
# M2 — Write path
# ---------------------------------------------------------------------------


@pytest.mark.callish_milestone("m2")
def test_m2_create_assigns_pk(conform_model):
    obj = conform_model(number="NEW", amount_cents=100, paid=False)
    assert obj.pk is None
    obj.save()
    assert obj.pk is not None
    # Round-trip: fetch by pk should return the same.
    refetched = conform_model.objects.get(pk=obj.pk)
    assert refetched.number == "NEW"


@pytest.mark.callish_milestone("m2")
def test_m2_create_minimal(conform_model):
    obj = conform_model(number="MIN")
    obj.save()
    assert obj.pk is not None


@pytest.mark.callish_milestone("m2")
def test_m2_update_round_trip(conform_model):
    obj = conform_model.objects.create(
        number="ORIG", amount_cents=100, paid=False
    )
    obj.paid = True
    obj.save()
    refreshed = conform_model.objects.get(pk=obj.pk)
    assert refreshed.paid is True


@pytest.mark.callish_milestone("m2")
def test_m2_update_missing(conform_model):
    obj = conform_model(number="GHOST", amount_cents=0, paid=False)
    obj.pk = 999_999
    with pytest.raises(NotFound):
        obj.save()


@pytest.mark.callish_milestone("m2")
def test_m2_delete(conform_model):
    obj = conform_model.objects.create(
        number="DELME", amount_cents=0, paid=False
    )
    pk = obj.pk
    obj.delete()
    with pytest.raises(conform_model.DoesNotExist):
        conform_model.objects.get(pk=pk)


# ---------------------------------------------------------------------------
# M3 — Error / timeout mapping
# ---------------------------------------------------------------------------


def _maybe_skip_m3(adapter) -> None:
    if not hasattr(adapter, "set_failure_mode"):
        pytest.skip(
            "adapter does not expose set_failure_mode(); cannot exercise M3 "
            "error paths against this implementation"
        )


@pytest.mark.callish_milestone("m3")
def test_m3_unauthorized_propagates(conform_model):
    adapter = conform_model._callish_adapter
    _maybe_skip_m3(adapter)
    adapter.set_failure_mode("unauthorized")
    with pytest.raises(Unauthorized):
        list(conform_model.objects.all())


@pytest.mark.callish_milestone("m3")
def test_m3_upstream_5xx_propagates(conform_model):
    adapter = conform_model._callish_adapter
    _maybe_skip_m3(adapter)
    adapter.set_failure_mode("upstream5xx")
    with pytest.raises(Upstream5xx):
        list(conform_model.objects.all())


@pytest.mark.callish_milestone("m3")
def test_m3_rate_limited_propagates(conform_model):
    adapter = conform_model._callish_adapter
    _maybe_skip_m3(adapter)
    adapter.set_failure_mode("ratelimited")
    with pytest.raises(RateLimited):
        list(conform_model.objects.all())


@pytest.mark.callish_milestone("m3")
def test_m3_adapter_validation_has_field_errors(conform_model):
    adapter = conform_model._callish_adapter
    _maybe_skip_m3(adapter)
    adapter.set_failure_mode(
        "validation",
        validation_errors={"number": ["must be unique"]},
    )
    with pytest.raises(AdapterValidationError) as exc_info:
        conform_model.objects.create(
            number="DUPE", amount_cents=0, paid=False
        )
    assert exc_info.value.errors.get("number") == ["must be unique"]
