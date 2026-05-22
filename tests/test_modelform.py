"""APIModelForm — fields_for_model introspection + save() → adapter."""

from __future__ import annotations

import pytest
from django import forms
from django.forms.models import fields_for_model

from .models import Invoice, InvoiceForm


def test_fields_for_model_introspects_apimodel(invoice_model):
    fields = fields_for_model(invoice_model, fields=("number", "amount_cents", "paid"))
    assert isinstance(fields["number"], forms.CharField)
    assert isinstance(fields["amount_cents"], forms.IntegerField)
    assert isinstance(fields["paid"], forms.BooleanField)


def test_form_renders_fields():
    form = InvoiceForm()
    rendered = form.as_p()
    assert 'name="number"' in rendered
    assert 'name="amount_cents"' in rendered
    assert 'name="paid"' in rendered


def test_form_save_creates_via_adapter(inmemory_adapter):
    form = InvoiceForm(data={"number": "FORM-1", "amount_cents": "500", "paid": "on"})
    assert form.is_valid(), form.errors
    instance = form.save()
    assert instance.pk is not None
    assert inmemory_adapter.calls["create"] == 1
    # Round-trip via the manager.
    fetched = Invoice.objects.get(pk=instance.pk)
    assert fetched.number == "FORM-1"


def test_form_save_updates_existing(inmemory_adapter):
    existing = Invoice.objects.create(number="OG", amount_cents=10, paid=False)
    form = InvoiceForm(
        data={"number": "OG-UPDATED", "amount_cents": "10", "paid": ""},
        instance=existing,
    )
    assert form.is_valid(), form.errors
    inmemory_adapter.calls["update"] = 0
    inmemory_adapter.calls["create"] = 0
    form.save()
    assert inmemory_adapter.calls["update"] == 1
    assert inmemory_adapter.calls["create"] == 0
    assert Invoice.objects.get(pk=existing.pk).number == "OG-UPDATED"


def test_form_save_commit_false_does_not_call_adapter(inmemory_adapter):
    form = InvoiceForm(data={"number": "DRAFT", "amount_cents": "1", "paid": ""})
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    assert inmemory_adapter.calls["create"] == 0
    assert instance.number == "DRAFT"


def test_form_validation_errors_for_missing_required():
    form = InvoiceForm(data={"number": "", "amount_cents": "", "paid": ""})
    assert not form.is_valid()
    assert "number" in form.errors
    assert "amount_cents" in form.errors


def test_form_save_surfaces_adapter_validation_error(inmemory_adapter):
    from callish.exceptions import AdapterValidationError

    inmemory_adapter.set_failure_mode(
        "validation", validation_errors={"number": ["taken"]}
    )
    form = InvoiceForm(data={"number": "DUPE", "amount_cents": "1", "paid": ""})
    assert form.is_valid()
    with pytest.raises(AdapterValidationError):
        form.save()
    # After save() rejects, the form's non-field/field errors carry the info.
    assert "taken" in str(form.errors.get("number", []))
