"""M3 — error propagation and DoesNotExist mapping."""

from __future__ import annotations

import pytest

from callish.exceptions import (
    AdapterValidationError,
    NotFound,
    RateLimited,
    Unauthorized,
    Upstream5xx,
)


def test_notfound_maps_to_does_not_exist(invoice_model):
    with pytest.raises(invoice_model.DoesNotExist):
        invoice_model.objects.get(pk=12345)


def test_notfound_remains_notfound_on_raw_adapter_calls(invoice_model):
    obj = invoice_model(number="X")
    obj.pk = 999
    with pytest.raises(NotFound):
        obj.refresh_from_db()


def test_unauthorized_propagates_on_list(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.set_failure_mode("unauthorized")
    with pytest.raises(Unauthorized):
        list(invoice_model.objects.all())


def test_unauthorized_propagates_on_create(invoice_model, inmemory_adapter):
    inmemory_adapter.set_failure_mode("unauthorized")
    with pytest.raises(Unauthorized):
        invoice_model.objects.create(number="X")


def test_rate_limited_carries_retry_after(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.set_failure_mode("ratelimited")
    with pytest.raises(RateLimited) as exc_info:
        list(invoice_model.objects.all())
    assert exc_info.value.retry_after == 1.0


def test_upstream_5xx_carries_status(seeded, invoice_model, inmemory_adapter):
    inmemory_adapter.set_failure_mode("upstream5xx")
    with pytest.raises(Upstream5xx) as exc_info:
        list(invoice_model.objects.all())
    assert exc_info.value.status == 502


def test_adapter_validation_error_carries_field_errors(invoice_model, inmemory_adapter):
    inmemory_adapter.set_failure_mode(
        "validation", validation_errors={"number": ["must be unique"]}
    )
    with pytest.raises(AdapterValidationError) as exc_info:
        invoice_model.objects.create(number="DUPE")
    assert exc_info.value.errors == {"number": ["must be unique"]}
