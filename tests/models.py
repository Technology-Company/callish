"""Shared APIModel + adapter used across the library's own test suite.

The adapter is module-level so ``tests/urls.py`` and ``tests/views.py`` can
import the *same* model the test fixtures mutate. Tests must call
``ADAPTER.reset()`` between scenarios (the ``inmemory_adapter`` fixture does
this automatically).
"""

from __future__ import annotations

from callish import APIModel, APIModelForm
from callish.fields import BooleanField, CharField, IntegerField
from callish.testing import InMemoryAdapter

ADAPTER = InMemoryAdapter()


class Invoice(APIModel):
    id = IntegerField(primary_key=True)
    number = CharField(max_length=64)
    amount_cents = IntegerField()
    paid = BooleanField(default=False)

    class Meta:
        adapter = ADAPTER
        app_label = "tests"
        verbose_name = "invoice"
        verbose_name_plural = "invoices"


class InvoiceForm(APIModelForm):
    class Meta:
        model = Invoice
        fields = ["number", "amount_cents", "paid"]
