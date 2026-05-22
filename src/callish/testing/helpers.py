"""Helpers for building conformance fixtures."""

from __future__ import annotations

from typing import Any, Protocol

from .. import fields as cf
from ..models import APIModel


class AdapterFactory(Protocol):
    """Callable that returns a fresh adapter instance for each test."""

    def __call__(self) -> Any: ...


def make_invoice_model(adapter: Any, *, name: str = "Invoice") -> type[APIModel]:
    """Build a canonical ``Invoice``-shaped APIModel pointed at ``adapter``.

    Used by the conformance suite so users don't have to redeclare the model
    just to run the tests. Adapters are expected to round-trip these field
    names: ``id`` (int pk), ``number`` (str), ``amount_cents`` (int),
    ``paid`` (bool).
    """

    attrs: dict[str, Any] = {
        "id": cf.IntegerField(primary_key=True),
        "number": cf.CharField(max_length=64),
        "amount_cents": cf.IntegerField(),
        "paid": cf.BooleanField(default=False),
        "Meta": type("Meta", (), {"adapter": adapter, "app_label": "conform"}),
    }
    return type(name, (APIModel,), attrs)
