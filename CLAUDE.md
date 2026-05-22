# callish — Django QuerySet façade for API adapters

## What this project is

`callish` lets a Django app expose data living behind an arbitrary API as if it
were a Django model — so `ModelForm`, generic views, templates, and admin
register/instantiation keep working — **without** standardising the HTTP shape.
You write the adapter (`list / retrieve / create / update / delete`); `callish`
wires it into Django.

It is **not** Wagtail/Snippet/Chooser integration, **not** an ORM bridge, and
**not** a code generator. See `callish-spec.md` for the full spec and explicit
non-goals.

## Layout

```
src/callish/
  models.py        APIModel + APIModelMetaclass (builds the _meta shim)
  _meta.py         Options shim exposing the surface Django introspects
  fields.py        Re-exports django.db.models.fields.* (used standalone)
  queryset.py      APIQuerySet — lazy, state-accumulating queryset
  manager.py       APIManager (.objects)
  forms.py         APIModelForm — ModelForm that talks to adapters
  adapter.py       AdapterProtocol + BaseAdapter
  exceptions.py    AdapterError + NotFound/Unauthorized/RateLimited/Upstream5xx/AdapterValidationError
  apps.py          Inert AppConfig (no signals, no patching — Wagtail-safe)
  testing/
    reference_adapter.py   InMemoryAdapter (dict-backed, supports failure modes)
    suite.py               Shipping conformance tests (M1/M2/M3 milestones)
    plugin.py              pytest11 plugin (auto-loaded by `pip install callish`)
    helpers.py             make_invoice_model()
tests/                     This library's own tests (use InMemoryAdapter)
```

## Setup

```bash
poetry install                  # core + dev deps
poetry install --with compat    # + Wagtail, for the coexistence smoke test
```

Supported runtime: **Python ≥3.10, Django ≥5.0 <7.0**. Tested on Django 5.x
and Django 6.x. Coexists with Wagtail 6.x (on Django 5) and Wagtail 7.x (on
Django 5 or 6).

## Declaring an APIModel

```python
from callish import APIModel
from callish.fields import CharField, IntegerField, BooleanField

class Invoice(APIModel):
    id = IntegerField(primary_key=True)
    number = CharField(max_length=64)
    amount_cents = IntegerField()
    paid = BooleanField(default=False)

    class Meta:
        # Adapter can be an instance, a class, or "pkg.mod:Class" / "pkg.mod.Class".
        adapter = "myproject.adapters.invoices:InvoiceAdapter"
        app_label = "myproject"
```

## Writing an adapter

Any object with these five methods works (duck-typed via `AdapterProtocol`):

```python
class InvoiceAdapter:
    def list(self, *, filters, ordering, offset, limit): ...     # → list of dicts
    def retrieve(self, pk): ...                                  # → dict; raise NotFound if missing
    def create(self, data): ...                                  # → dict (with assigned pk)
    def update(self, pk, data): ...                              # → dict; raise NotFound if missing
    def delete(self, pk): ...                                    # raise NotFound if missing
    def count(self, *, filters): ...                             # optional; return None to fall back
```

Errors: raise `callish.exceptions.NotFound / Unauthorized / RateLimited /
Upstream5xx / AdapterValidationError`. `NotFound` is mapped to the model's
`DoesNotExist`; the rest surface as-is.

For an example that round-trips real data, see
`src/callish/testing/reference_adapter.py` (`InMemoryAdapter`).

## Using it in Django code

```python
# Standard QuerySet shapes
qs = Invoice.objects.filter(paid=False).order_by("-amount_cents")[:25]
for invoice in qs:                                # → adapter.list()
    ...

invoice = Invoice.objects.get(pk=42)              # → adapter.retrieve(42)
invoice.paid = True
invoice.save()                                    # → adapter.update(42, {...})

new = Invoice(number="INV-100", amount_cents=10_000, paid=False)
new.save()                                        # → adapter.create({...}); pk filled in

invoice.delete()                                  # → adapter.delete(42)
```

### ModelForm

```python
from callish import APIModelForm

class InvoiceForm(APIModelForm):
    class Meta:
        model = Invoice
        fields = ["number", "amount_cents", "paid"]

form = InvoiceForm(data=request.POST, instance=invoice_or_none)
if form.is_valid():
    form.save()                                   # → adapter.create or .update
```

`_post_clean()` skips DB-constraint validation; the adapter is the source of
truth for upstream validation. `AdapterValidationError` raised during `save()`
is translated to a form-level `ValidationError` so per-field messages display.

### Generic class-based views

`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView` all work
out of the box. `tests/test_generic_views.py` shows the complete pattern.
Generic views call `queryset.filter(pk=...)`; callish translates `pk` to your
declared pk field name so the adapter receives the real field.

### Function-based views

```python
def invoice_summary(request):
    unpaid = Invoice.objects.filter(paid=False)
    return JsonResponse({"total": sum(i.amount_cents for i in unpaid)})
```

See `tests/test_views_function_based.py` for `.get`, `.filter`, `.create`,
JSON-body create, and DoesNotExist → 404 patterns.

### Templates

Just works — `{% for invoice in invoices %}`, `{{ invoice.number }}`,
`{{ form.as_p }}` etc. The generic-view tests assert against rendered HTML
to prove this end-to-end.

### Admin

`admin.site.register([Invoice], InvoiceAdmin)` (note the **list wrap** — the
bare-class form does `isinstance(model, ModelBase)` and falls into iteration).
`ModelAdmin` instances construct fine. **Changelist is a non-goal per spec**
— admin's changelist machinery assumes a real Django Model with a DB table.

## Running tests

```bash
poetry run pytest                                 # library's own suite (94 tests)
poetry run pytest --pyargs callish.testing.suite  # shipping conformance suite (20 tests)
poetry run ruff check src tests
poetry run mypy src/callish
```

## Conformance suite (for downstream adapter authors)

If you've written an adapter, verify it satisfies the contract by adding one
fixture to your conftest and running the shipping suite:

```python
# your_project/conftest.py
import pytest
from your_project.adapters import StripeInvoiceAdapter

@pytest.fixture
def conform_adapter():
    return StripeInvoiceAdapter(api_key="sk_test_...")
```

```bash
pytest --pyargs callish.testing.suite
```

The pytest plugin (auto-loaded via `pytest11` entry point) injects the
`conform_model` fixture and adds `--callish-skip-m3` for incremental adoption.

Milestones:
- **M1** — list / retrieve / count / filter / order / slice
- **M2** — create / update / delete
- **M3** — error and timeout propagation

To opt out of auto-loading in a project that doesn't want it:
`pytest -p no:callish`.

## Notes on Wagtail coexistence

`callish.apps.CallishConfig` is intentionally inert — no signal receivers,
no Django monkey-patching, no admin-site mutations at import time. Add
`callish` to `INSTALLED_APPS` alongside `wagtail` and nothing breaks.
`tests/compat/test_wagtail_smoke.py` is the opt-in smoke test (install
the `compat` Poetry group to run it).

## Where to read what

- **Spec & rationale**: `callish-spec.md`
- **How to write an adapter**: `src/callish/testing/reference_adapter.py`
- **What Django sees**: `src/callish/_meta.py` (the shim is small; read it)
- **Examples of every Django integration**: the `tests/` tree mirrors the
  surface area, file-per-concern (`test_modelform.py`, `test_generic_views.py`,
  `test_views_function_based.py`, `test_admin.py`, ...).
