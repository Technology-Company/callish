"""Field wrappers produce sensible form fields and round-trip values."""

from __future__ import annotations

from django import forms
from django.db import models as dj_models

from callish import fields as cf


def test_charfield_is_django_charfield():
    f = cf.CharField(max_length=64)
    assert isinstance(f, dj_models.CharField)
    assert f.max_length == 64


def test_charfield_yields_charfield_formfield():
    f = cf.CharField(max_length=64)
    form_field = f.formfield()
    assert isinstance(form_field, forms.CharField)
    assert form_field.max_length == 64


def test_integerfield_yields_integerfield_formfield():
    f = cf.IntegerField()
    form_field = f.formfield()
    assert isinstance(form_field, forms.IntegerField)


def test_booleanfield_default_is_falsy():
    f = cf.BooleanField(default=False)
    assert f.has_default()
    assert f.get_default() is False


def test_charfield_with_choices_yields_typedchoicefield_or_charfield():
    f = cf.CharField(max_length=4, choices=[("a", "A"), ("b", "B")])
    form_field = f.formfield()
    # Django returns a TypedChoiceField when choices is set.
    assert hasattr(form_field, "choices")
