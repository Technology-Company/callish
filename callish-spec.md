# callish — Django QuerySet façade for user-written API adapters

## Mission

`callish` lets a Django app expose data that lives behind an arbitrary API as
if it were a Django model — so `ModelForm`, generic views, templates, and the
admin can keep working — **without** trying to standardise the HTTP shape.
You write the calls (the "adapter"); `callish` wires them into Django.

Prior art: `wagtail/queryish` (read-only, REST-only, no test battery).
`callish` differs in three deliberate ways:

1. **Full CRUD** out of the box.
2. **User-supplied adapter** — APIs vary too much for one base class to fit.
   You write `list / retrieve / create / update / delete`; `callish` calls them.
3. **A conformance test battery** is the spec. You write your adapter against
   the test suite — when the tests are green, Django integration works.

## Non-goals (v1)

- Cross-source joins (API model ↔ ORM model)
- Relations between API models (FK, M2M, prefetch)
- Async adapters (sync only)
- ModelAdmin changelist (likely doesn't compose with non-Model `_meta`;
  documented as a known boundary, not a bug)
- Code generation from OpenAPI / GraphQL schemas
- Wagtail Snippet / Chooser integration

## Architecture — three layers

```
+-----------------------------+
|  Django: ModelForm,         |     <— unchanged Django
|  ListView, templates, etc.  |
+--------------+--------------+
               |
+--------------v--------------+
|  callish façade:            |
|  APIModel, APIQuerySet,     |     <— this library
|  APIManager, APIModelForm,  |
|  _meta shim                 |
+--------------+--------------+
               |
+--------------v--------------+
|  Adapter (user-written):    |     <— user code
|  list/retrieve/create/...   |     <— calls REST / GraphQL / fake / whatever
+-----------------------------+
```

## Adapter contract (the spec)

```python
from typing import Protocol, Mapping, Sequence, Any

class AdapterProtocol(Protocol):
    def list(
        self, *,
        filters: Mapping[str, Any],
        ordering: Sequence[str],    
        offset: int,
        limit: int | None,
    ) -> Sequence[Mapping[str, Any]]: ...

    def retrieve(self, pk: Any) -> Mapping[str, Any]: ...
    def create(self, data: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def update(self, pk: Any, data: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def delete(self, pk: Any) -> None: ...

    # Optional. Return None ⇒ "I don't know", façade falls back to len(list(...))
    def count(self, *, filters: Mapping[str, Any]) -> int | None: ...
```

**Errors**: adapter raises subclasses of `callish.exceptions.AdapterError`:
`NotFound, Unauthorized, RateLimited, Upstream5xx, AdapterValidationError`.
The façade maps `NotFound` → Django `DoesNotExist`; surfaces the rest as-is.

This contract is intentionally narrow. Anything HTTP-specific (auth, retries,
backoff, JSON parsing) lives in the adapter, not in `callish`.

## Model declaration (user side)

```python
from callish import APIModel
from callish.fields import CharField, IntegerField, BooleanField

class Invoice(APIModel):
    id = IntegerField(primary_key=True)
    number = CharField(max_length=64)
    amount_cents = IntegerField()
    paid = BooleanField()

    class Meta:
        adapter = "myproject.adapters.invoices:InvoiceAdapter"
```

`fields` are thin wrappers around `django.db.models.fields.*` *instances* —
declared but never attached to a DB table. They exist so `ModelForm`'s
`fields_for_model()` can introspect types.

## CRUD usage (caller side, unchanged Django shapes)

```python
qs = Invoice.objects.filter(paid=False).order_by("-amount_cents")[:25]
for invoice in qs:                                 # adapter.list()
    print(invoice.number, invoice.amount_cents)

invoice = Invoice.objects.get(pk=42)               # adapter.retrieve(42)
invoice.paid = True
invoice.save()                                     # adapter.update(42, {...})

new = Invoice(number="INV-100", amount_cents=10_000, paid=False)
new.save()                                         # adapter.create({...}), pk filled in

invoice.delete()                                   # adapter.delete(42)
```

## The conformance test battery

Ships as a pytest plugin. Registered as a `pytest11` entry point in
`pyproject.toml`, so just installing `callish` is enough — pytest finds it.
The user supplies a `conform_adapter` fixture:

```python
# user's conftest.py
import pytest
from myproject.adapters.invoices import InvoiceAdapter

@pytest.fixture
def conform_adapter():
    yield InvoiceAdapter(base_url="https://example.test/")
```

Then:

```bash
pytest --pyargs callish.testing.suite
```

To disable the plugin in a project that doesn't want it auto-loaded:
`pytest -p no:callish`.

### What the suite covers — milestone-organised (mirrors `django-rust-orm`)

- **M1.list** — empty / single / many; offset+limit honoured; ordering applied
- **M1.retrieve** — by pk; `NotFound` on missing
- **M1.filter** — equality, `__in`, `__gte`, `__contains` if declared supported
- **M2.create** — minimal payload; server-assigned pk; partial validation
- **M2.update** — full and partial; absent pk → `NotFound`
- **M2.delete** — exists → gone; idempotency optional
- **M3.errors** — `Unauthorized` propagates; `Upstream5xx` propagates;
  `AdapterValidationError` surfaces field-level info
- **M3.timeouts** — adapter respects whatever timeout the user configured

Each test has a precise failure message tied to the contract clause it
exercises. Users implement adapters incrementally — green M1 first, then M2,
then M3. Green M1+M2 = `ModelForm` and generic views work.

A `callish.testing.reference_adapter:InMemoryAdapter` ships as a tiny example
adapter the suite runs against itself — both as a smoke test for the library
and as a reference for users writing their first adapter.

## Django integration details (the load-bearing engineering)

- **`_meta` shim** in `callish/_meta.py` exposing `pk`, `concrete_fields`,
  `fields`, `get_field()`, `app_label`, `model_name`, `object_name`,
  `verbose_name`, `verbose_name_plural`. Spike this against
  `modelform_factory` before committing to the API shape — if Django's
  `ModelFormMetaclass` rejects non-`Model` instances at class-construction
  time, fall back to a hand-rolled `APIModelForm` base that bypasses
  `modelform_factory` entirely.
- **`APIModelForm`** — overrides `_post_clean()` to skip DB-constraint
  validation, and `save()` to dispatch to `adapter.create()` /
  `adapter.update()` based on `self.instance.pk`.
- **`APIManager` + `APIQuerySet`** — chainable filter/order_by/slice that
  *accumulate* state and only call the adapter on iteration / `len()` /
  `get()`.

## Settings (downstream Django project)

```python
INSTALLED_APPS = [..., "callish"]
CALLISH_DEFAULT_TIMEOUT = 5  # seconds; adapter is free to ignore
# Optional dotted-path registry; mostly useful for tests
CALLISH_ADAPTERS = {"invoices": "myproject.adapters.invoices:InvoiceAdapter"}
```

## Packaging

- **Runtime**: depends only on Django. `pip install callish` and you can
  declare `APIModel`s, wire adapters, render forms / views — no pytest is
  imported at runtime.
- **Dev group** (Poetry `[tool.poetry.group.dev.dependencies]`): pytest, ruff,
  mypy. Pytest lives here because (a) the library's own tests use it, (b)
  downstream projects that want to run the conformance suite need it but
  almost always already have it as their own dev dep — installing `callish`
  then doesn't pull anything extra.
- **pytest plugin auto-discovery**: registered via `[project.entry-points.pytest11]`.
  Inert when pytest isn't installed. End users get the conformance suite with
  no extra setup beyond having pytest (which they almost always do).
- **No `[testing]` extra.** One installation path, one way to run the suite.

## Repo layout

```
callish/
├── pyproject.toml
├── README.md
├── LICENSE                     # BSD-3-Clause
├── CHANGELOG.md
├── src/callish/
│   ├── __init__.py             # re-exports APIModel, APIQuerySet, APIManager
│   ├── apps.py                 # CallishConfig
│   ├── models.py               # APIModel
│   ├── fields.py
│   ├── queryset.py             # APIQuerySet
│   ├── manager.py              # APIManager
│   ├── forms.py                # APIModelForm
│   ├── exceptions.py
│   ├── adapter.py              # AdapterProtocol + BaseAdapter
│   ├── _meta.py                # the shim
│   └── testing/
│       ├── __init__.py         # re-exports InMemoryAdapter for convenience
│       ├── suite.py            # the pytest conformance tests (test_m1_*, test_m2_*, …)
│       ├── plugin.py           # pytest plugin: registers fixtures, CLI options
│       ├── reference_adapter.py# InMemoryAdapter — self-test target and user reference
│       └── helpers.py          # adapter-factory protocol, reset helpers
├── tests/                      # the library's OWN tests (uses InMemoryAdapter)
├── examples/django_demo/       # runnable mini-Django project showing form+listview
└── docs/
    ├── adapter-guide.md
    ├── conformance.md
    └── django-integration.md
```

## `pyproject.toml` (canonical shape)

```toml
[project]
name = "callish"
version = "0.1.0"
description = "Django QuerySet façade for user-written API adapters."
requires-python = ">=3.10"
dependencies = ["django>=5.0"]
license = { text = "BSD-3-Clause" }

[project.entry-points.pytest11]
callish = "callish.testing.plugin"

[tool.poetry]
package-mode = true

[tool.poetry.group.dev.dependencies]
pytest = ">=8,<9"
ruff = ">=0.6"
mypy = ">=1.10"

[tool.pytest.ini_options]
addopts = "-ra"
python_files = ["test_*.py"]
```

## Tech choices

- Python 3.10+ (Protocol + structural typing)
- Django 5.x + 6.x supported; test matrix via tox or nox
- **No HTTP client dependency** — that's the adapter's problem
- BSD-3-Clause (matches queryish)
- Versioning: 0.x while the adapter contract is in flux; 1.0 freezes it

## Milestones

| M  | What                                                              | Done when                                                              |
| -- | ----------------------------------------------------------------- | ---------------------------------------------------------------------- |
| M1 | Read path (list/retrieve/count/filter/order/slice)                | `examples/django_demo` ListView + DetailView render                   |
| M2 | Write path (create/update/delete, APIModelForm.save)              | `examples/django_demo` Create+UpdateView round-trip                   |
| M3 | Error/timeout mapping                                             | Conformance suite has zero xfails against `InMemoryAdapter`            |
| M4 | Polish: docs, type hints, type-check clean, py3.10–3.13 matrix    | Ready for PyPI 0.1                                                     |

## Open design questions (resolve before M1)

1. **Filter expressiveness** — does `qs.filter(name__icontains="foo")` pass
   through as `{"name__icontains": "foo"}` to `adapter.list(filters=...)`, or
   do we restrict to equality only? Recommendation: pass through verbatim;
   adapter advertises support via a `supported_lookups` class attribute;
   conformance tests skip lookups the adapter doesn't claim.
2. **Server-assigned pks vs client-assigned** — `create()` returns the new
   record; how does `instance.pk` get refreshed? Recommendation: façade
   reassigns from the returned dict's pk field.
3. **Bulk operations** — `qs.update(**fields)`, `qs.delete()` — required for
   v1 or deferred? Recommendation: defer; document as M2.5.
4. **Caching** — per-process queryset cache like queryish has? Recommendation:
   yes, keyed on the canonical filter+order+slice tuple; invalidated on any
   `create/update/delete` for the same model.

## Bootstrapping prompt (to hand to a Claude session in a new clone)

> Create a new Python package `callish` at `/Users/johanna/Documents/GitHub/callish/`.
> Spec is in `/Users/johanna/Documents/GitHub/huma-project/callish-spec.md`. Start with M1:
> scaffold `pyproject.toml` per the spec (Python 3.10+, Django 5+/6+,
> BSD-3-Clause, pytest in the dev group, pytest11 entry point registered),
> the `src/callish/` tree from the spec, and the `InMemoryAdapter` reference.
> Write `tests/` against the reference adapter. Get `examples/django_demo` to
> render an Invoice ListView before moving to M2. Mirror django-rust-orm's
> test naming convention (`test_m1_*.py`, `test_m2_*.py`). Do not add an HTTP
> client dependency.
