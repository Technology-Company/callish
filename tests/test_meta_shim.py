"""``_meta`` shim exposes the surface Django introspects."""

from __future__ import annotations

import pytest
from django.core.exceptions import FieldDoesNotExist


def test_meta_basic_attrs(invoice_model):
    meta = invoice_model._meta
    assert meta.app_label == "tests"
    assert meta.object_name == "Invoice"
    assert meta.model_name == "invoice"
    assert meta.verbose_name == "invoice"
    assert meta.verbose_name_plural == "invoices"


def test_meta_label_and_label_lower(invoice_model):
    meta = invoice_model._meta
    assert meta.label == "tests.Invoice"
    assert meta.label_lower == "tests.invoice"


def test_meta_concrete_fields_includes_declarations(invoice_model):
    names = [f.name for f in invoice_model._meta.concrete_fields]
    assert names == ["id", "number", "amount_cents", "paid"]


def test_meta_pk_points_at_id(invoice_model):
    assert invoice_model._meta.pk.name == "id"


def test_meta_get_field_known(invoice_model):
    field = invoice_model._meta.get_field("number")
    assert field.name == "number"


def test_meta_get_field_pk_alias(invoice_model):
    field = invoice_model._meta.get_field("pk")
    assert field.name == "id"


def test_meta_get_field_unknown(invoice_model):
    with pytest.raises(FieldDoesNotExist):
        invoice_model._meta.get_field("nope")


def test_meta_many_to_many_and_private_fields_are_empty(invoice_model):
    assert invoice_model._meta.many_to_many == []
    assert invoice_model._meta.private_fields == []


def test_meta_callish_shim_marker(invoice_model):
    assert getattr(invoice_model._meta, "callish_shim", False) is True
