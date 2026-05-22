"""URL patterns used by tests/test_generic_views.py.

Defined here (not inside the test) so Django's URL reverse machinery can
resolve names like ``invoice-list`` from anywhere in the suite.
"""

from __future__ import annotations

from django.contrib import admin
from django.urls import path

from .views import (
    InvoiceCreateView,
    InvoiceDeleteView,
    InvoiceDetailView,
    InvoiceListView,
    InvoiceUpdateView,
    invoice_create_json,
    invoice_deleted_ok,
    invoice_mark_paid,
    invoice_search,
    invoice_summary,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Generic class-based views
    path("invoices/", InvoiceListView.as_view(), name="invoice-list"),
    path("invoices/new/", InvoiceCreateView.as_view(), name="invoice-create"),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view(), name="invoice-detail"),
    path(
        "invoices/<int:pk>/edit/", InvoiceUpdateView.as_view(), name="invoice-update"
    ),
    path(
        "invoices/<int:pk>/delete/",
        InvoiceDeleteView.as_view(),
        name="invoice-delete",
    ),
    path("invoices/deleted/", invoice_deleted_ok, name="invoice-deleted"),
    # Function-based views
    path("api/invoices/summary/", invoice_summary, name="invoice-summary"),
    path("api/invoices/search/", invoice_search, name="invoice-search"),
    path(
        "api/invoices/<int:pk>/pay/", invoice_mark_paid, name="invoice-mark-paid"
    ),
    path("api/invoices/", invoice_create_json, name="invoice-create-json"),
]
