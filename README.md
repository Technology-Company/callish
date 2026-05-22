# callish

**Django QuerySet façade for user-written API adapters.**

`callish` lets a Django app expose data living behind an arbitrary API as if
it were a Django model — so `ModelForm`, generic class-based views, templates,
and admin register/instantiation keep working — **without** trying to
standardise the HTTP shape. You write the adapter (`list / retrieve / create /
update / delete`); `callish` wires it into Django.

Status: **0.x**, adapter contract is still in flux. 1.0 freezes it.

## Why

Existing libraries either lock you into a specific HTTP shape
(`wagtail/queryish` — REST-only, read-only) or rebuild Django machinery
from scratch. APIs vary too much for one base class to fit all of them.
callish takes the opposite stance: you write the five-method adapter, and
callish handles the Django integration around it.

The conformance suite is the spec — when the test battery is green, Django
integration works.

## Install

```bash
pip install callish      # core
# or, with Poetry:
poetry add callish
```

**Requires** Python ≥3.10, Django ≥5.0 (5.x or 6.x). No HTTP client
dependency — that's the adapter's job.

## Quick start

```python
from callish import APIModel, APIModelForm
from callish.fields import CharField, IntegerField, BooleanField


class Invoice(APIModel):
    id = IntegerField(primary_key=True)
    number = CharField(max_length=64)
    amount_cents = IntegerField()
    paid = BooleanField(default=False)

    class Meta:
        adapter = "myproject.adapters:InvoiceAdapter"
        app_label = "myproject"


# Use it like a Django model:
qs = Invoice.objects.filter(paid=False).order_by("-amount_cents")[:25]
for invoice in qs:                                # → adapter.list(...)
    print(invoice.number, invoice.amount_cents)

invoice = Invoice.objects.get(pk=42)              # → adapter.retrieve(42)
invoice.paid = True
invoice.save()                                    # → adapter.update(42, {...})

new = Invoice(number="INV-100", amount_cents=10_000, paid=False)
new.save()                                        # → adapter.create({...})

invoice.delete()                                  # → adapter.delete(42)
```

## Writing an adapter

Any object with these methods works:

```python
class InvoiceAdapter:
    def list(self, *, filters, ordering, offset, limit): ...     # → Sequence[dict]
    def retrieve(self, pk): ...                                  # → dict
    def create(self, data): ...                                  # → dict (with pk)
    def update(self, pk, data): ...                              # → dict
    def delete(self, pk): ...
    def count(self, *, filters): ...                             # optional
```

Raise `callish.exceptions.NotFound / Unauthorized / RateLimited /
Upstream5xx / AdapterValidationError` for errors. `NotFound` is mapped to
the model's `DoesNotExist`; the rest surface as-is.

A complete reference implementation lives in
[`src/callish/testing/reference_adapter.py`](src/callish/testing/reference_adapter.py)
(`InMemoryAdapter` — dict-backed, used by callish's own tests).

## Django integration

Everything you'd expect from a Django model works:

- **ModelForm** — subclass `APIModelForm`; `form.save()` dispatches to
  `adapter.create` / `adapter.update`.
- **Generic class-based views** — `ListView`, `DetailView`, `CreateView`,
  `UpdateView`, `DeleteView` all work unchanged.
- **Function-based views** — `Invoice.objects.filter(...)` inside any
  `def view(request)` function.
- **Templates** — `{% for invoice in invoices %}{{ invoice.number }}`,
  `{{ form.as_p }}` etc. all work.
- **Admin** — `admin.site.register([Invoice], InvoiceAdmin)` (note the list
  wrap) registers fine and `ModelAdmin` instances construct. The
  **changelist** is out of scope (admin assumes a real DB-backed Model).

## The conformance suite

`callish` ships a milestone-organised pytest suite that exercises the adapter
contract. Downstream adapter authors add one fixture and run:

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

The pytest plugin auto-loads via the `pytest11` entry point. To opt out:
`pytest -p no:callish`.

Milestones:
- **M1** — list / retrieve / count / filter / order / slice
- **M2** — create / update / delete
- **M3** — error and timeout propagation

Use `--callish-skip-m3` to skip error-path tests during incremental adoption.

## Non-goals (v1)

- Cross-source joins (API model ↔ ORM model)
- Relations between API models (FK, M2M, prefetch)
- Async adapters
- ModelAdmin changelist
- Code generation from OpenAPI / GraphQL schemas
- Wagtail Snippet / Chooser integration

callish coexists with Wagtail 6.x and 7.x without monkey-patching Django —
`callish.apps.CallishConfig` is intentionally inert.

## Development

```bash
poetry install                  # core + dev deps
poetry run pytest               # library suite (94 tests)
poetry run pytest --pyargs callish.testing.suite  # shipping conformance suite
poetry run ruff check src tests
poetry run mypy src/callish
```

The full spec is in [`callish-spec.md`](callish-spec.md). Architecture and
internals are documented in [`CLAUDE.md`](CLAUDE.md).

## License

BSD-3-Clause.