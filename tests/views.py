"""Test-only views wired against the shared Invoice APIModel.

Mix of generic class-based views and a few function-based views so the
suite covers both styles of Django view code.
"""

from __future__ import annotations

import json

from django.http import HttpResponse, JsonResponse
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .models import Invoice, InvoiceForm


class InvoiceListView(ListView):
    model = Invoice
    template_name = "invoice_list.html"
    context_object_name = "invoices"


class InvoiceDetailView(DetailView):
    model = Invoice
    template_name = "invoice_detail.html"
    context_object_name = "invoice"


class InvoiceCreateView(CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("invoice-list")


class InvoiceUpdateView(UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = "invoice_form.html"
    success_url = reverse_lazy("invoice-list")


class InvoiceDeleteView(DeleteView):
    model = Invoice
    template_name = "invoice_confirm_delete.html"
    success_url = reverse_lazy("invoice-deleted")


def invoice_deleted_ok(_request):
    return HttpResponse("deleted")


# ---------------------------------------------------------------------------
# Function-based views — showcase APIModel inside ad-hoc Django view code.
# ---------------------------------------------------------------------------


def invoice_summary(request):
    """Sum the cents of unpaid invoices, exercising filter + iteration."""
    unpaid = Invoice.objects.filter(paid=False)
    total = sum(inv.amount_cents for inv in unpaid)
    return JsonResponse({"unpaid_count": unpaid.count(), "total_cents": total})


def invoice_search(request):
    """Filter by query string — proves ``filter()`` flows through view kwargs."""
    qs = Invoice.objects.all()
    if (q := request.GET.get("q")):
        qs = qs.filter(number__icontains=q)
    return JsonResponse(
        {"numbers": [inv.number for inv in qs.order_by("amount_cents")]}
    )


@require_http_methods(["POST"])
def invoice_mark_paid(request, pk: int):
    """Look up by pk + mutate + save — the canonical view-level write flow."""
    try:
        invoice = Invoice.objects.get(pk=pk)
    except Invoice.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)
    invoice.paid = True
    invoice.save()
    return JsonResponse({"pk": invoice.pk, "paid": invoice.paid})


@require_http_methods(["POST"])
def invoice_create_json(request):
    """JSON-API style create — APIModel + json body + back to JSON response."""
    payload = json.loads(request.body.decode() or "{}")
    invoice = Invoice.objects.create(
        number=payload["number"],
        amount_cents=int(payload["amount_cents"]),
        paid=bool(payload.get("paid", False)),
    )
    return JsonResponse(
        {
            "pk": invoice.pk,
            "number": invoice.number,
            "amount_cents": invoice.amount_cents,
            "paid": invoice.paid,
        },
        status=201,
    )
