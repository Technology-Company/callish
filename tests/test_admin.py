"""Admin boundary tests.

Per the spec, ModelAdmin **changelist** is an explicit non-goal — admin
expects a real Django Model. We test only the surface that DOES compose:
``admin.site.register`` (with the list-wrap workaround) and ``ModelAdmin``
construction. The changelist HTTP path is out of scope and is not exercised.
"""

from __future__ import annotations

from django.contrib import admin

from .models import Invoice


class _InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "amount_cents", "paid")


def test_admin_register_does_not_raise():
    """``admin.site.register([Model], ...)`` works around the ``ModelBase`` check.

    ``site.register(Invoice, ...)`` does ``isinstance(Invoice, ModelBase)`` which
    is False for APIModel, so it falls through to ``for m in model_or_iterable``
    and tries to iterate the class. Passing a list (or any iterable) sidesteps
    that branch. This is a stable workaround we want to keep working.
    """
    site = admin.AdminSite(name="boundary-test-1")
    site.register([Invoice], _InvoiceAdmin)
    assert Invoice in site._registry


def test_modeladmin_instantiates():
    site = admin.AdminSite(name="boundary-test-2")
    admin_obj = _InvoiceAdmin(Invoice, site)
    assert admin_obj.model is Invoice
