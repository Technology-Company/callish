"""Lazy, state-accumulating queryset for API-backed models.

The queryset records ``filter``, ``order_by``, slice and exclude state
without calling the adapter. The adapter is only invoked when the queryset
is materialised (iterated, ``len()``-ed, ``.get()``-ed, etc.).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from django.core.exceptions import MultipleObjectsReturned

from .exceptions import NotFound

if TYPE_CHECKING:
    from .models import APIModel


class APIQuerySet:
    """Lazy queryset against an adapter.

    Chained calls accumulate state; the adapter is hit on materialisation.
    Per-instance result caching is keyed on the canonical (filters,
    ordering, slice) tuple — invalidated when the manager (or anything else)
    calls :meth:`_invalidate`.
    """

    def __init__(
        self,
        model: type[APIModel],
        *,
        filters: dict[str, Any] | None = None,
        excludes: list[dict[str, Any]] | None = None,
        ordering: tuple[str, ...] = (),
        offset: int = 0,
        limit: int | None = None,
    ) -> None:
        self.model = model
        self._filters: dict[str, Any] = dict(filters or {})
        self._excludes: list[dict[str, Any]] = [dict(e) for e in (excludes or [])]
        self._ordering: tuple[str, ...] = tuple(ordering)
        self._offset: int = offset
        self._limit: int | None = limit
        self._result_cache: list[APIModel] | None = None

    # ----- construction helpers -------------------------------------------

    def _clone(self, **overrides: Any) -> APIQuerySet:
        kwargs: dict[str, Any] = {
            "filters": self._filters,
            "excludes": self._excludes,
            "ordering": self._ordering,
            "offset": self._offset,
            "limit": self._limit,
        }
        kwargs.update(overrides)
        return type(self)(self.model, **kwargs)

    # ----- chainable queryset methods -------------------------------------

    def all(self) -> APIQuerySet:
        return self._clone()

    def none(self) -> APIQuerySet:
        empty = self._clone()
        empty._result_cache = []
        return empty

    def filter(self, **kwargs: Any) -> APIQuerySet:
        merged = {**self._filters, **self._normalize_pk(kwargs)}
        return self._clone(filters=merged)

    def exclude(self, **kwargs: Any) -> APIQuerySet:
        return self._clone(
            excludes=[*self._excludes, self._normalize_pk(kwargs)]
        )

    def _normalize_pk(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """Translate ``pk`` / ``pk__lookup`` to the actual pk field name.

        Django's generic views build filters as ``filter(pk=...)`` regardless
        of the model's pk field name — the adapter shouldn't have to know
        about the ``pk`` alias.
        """
        pk_name = self.model._meta.pk.name
        if pk_name == "pk":
            return dict(kwargs)
        out: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key == "pk":
                out[pk_name] = value
            elif key.startswith("pk__"):
                out[f"{pk_name}{key[2:]}"] = value
            else:
                out[key] = value
        return out

    def order_by(self, *fields: str) -> APIQuerySet:
        return self._clone(ordering=tuple(fields))

    # ----- materialisation -------------------------------------------------

    def _fetch(self) -> list[APIModel]:
        if self._result_cache is not None:
            return self._result_cache
        adapter = self.model._callish_adapter
        records = adapter.list(
            filters=dict(self._filters),
            ordering=list(self._ordering),
            offset=self._offset,
            limit=self._limit,
        )
        instances = [self.model._from_record(r) for r in records]
        instances = self._apply_excludes(instances)
        self._result_cache = instances
        return instances

    def _apply_excludes(self, instances: list[APIModel]) -> list[APIModel]:
        if not self._excludes:
            return instances
        kept: list[APIModel] = []
        for inst in instances:
            if any(self._matches(inst, ex) for ex in self._excludes):
                continue
            kept.append(inst)
        return kept

    @staticmethod
    def _matches(instance: APIModel, filters: dict[str, Any]) -> bool:
        for key, expected in filters.items():
            name = key.split("__", 1)[0]
            if getattr(instance, name, None) != expected:
                return False
        return True

    def _invalidate(self) -> None:
        self._result_cache = None

    # ----- Python protocol -------------------------------------------------

    def __iter__(self) -> Iterator[APIModel]:
        return iter(self._fetch())

    def __len__(self) -> int:
        return len(self._fetch())

    def __bool__(self) -> bool:
        return bool(self._fetch())

    def __getitem__(
        self, item: int | slice
    ) -> APIModel | list[APIModel] | APIQuerySet:
        if isinstance(item, int):
            if item < 0:
                raise ValueError("Negative indexing is not supported on APIQuerySet.")
            return self._fetch()[item]
        if not isinstance(item, slice):
            raise TypeError(f"APIQuerySet indices must be int or slice, not {type(item).__name__}")
        if item.step is not None:
            raise ValueError("APIQuerySet slicing does not support step.")
        start = item.start or 0
        stop = item.stop
        if self._result_cache is not None:
            return self._fetch()[start:stop]
        offset = self._offset + start
        limit: int | None
        if stop is None:
            limit = None if self._limit is None else max(self._limit - start, 0)
        else:
            span = stop - start
            if self._limit is not None:
                span = min(span, max(self._limit - start, 0))
            limit = max(span, 0)
        return self._clone(offset=offset, limit=limit)

    # ----- terminal helpers -----------------------------------------------

    def count(self) -> int:
        adapter = self.model._callish_adapter
        if hasattr(adapter, "count"):
            value = adapter.count(filters=dict(self._filters))
            if value is not None:
                if self._excludes:
                    # Excludes are evaluated client-side; we must materialise.
                    return len(self._fetch())
                return int(value)
        return len(self._fetch())

    def exists(self) -> bool:
        return self.count() > 0

    def first(self) -> APIModel | None:
        sliced = self[0:1]
        if isinstance(sliced, APIQuerySet):
            items: list[APIModel] = list(sliced)
        elif isinstance(sliced, list):
            items = sliced
        else:  # pragma: no cover — single-item slice cannot return a bare APIModel
            items = [sliced]
        return items[0] if items else None

    def last(self) -> APIModel | None:
        items = self._fetch()
        return items[-1] if items else None

    def get(self, **kwargs: Any) -> APIModel:
        pk_field = self.model._meta.pk.name
        adapter = self.model._callish_adapter

        # Fast path: ``get(pk=42)`` or ``get(<pkfield>=42)`` → adapter.retrieve.
        if set(kwargs).issubset({"pk", pk_field}) and len(kwargs) == 1:
            pk_value = next(iter(kwargs.values()))
            try:
                record = adapter.retrieve(pk_value)
            except NotFound as exc:
                raise self.model.DoesNotExist(
                    f"{self.model.__name__} matching query does not exist."
                ) from exc
            return self.model._from_record(record)

        qs = self.filter(**kwargs)
        sliced = qs[:2]
        if isinstance(sliced, APIQuerySet):
            results: list[APIModel] = list(sliced)
        elif isinstance(sliced, list):
            results = sliced
        else:  # pragma: no cover
            results = [sliced]
        if not results:
            raise self.model.DoesNotExist(
                f"{self.model.__name__} matching query does not exist."
            )
        if len(results) > 1:
            raise MultipleObjectsReturned(
                f"get() returned more than one {self.model.__name__}."
            )
        return results[0]

    def __repr__(self) -> str:
        try:
            sliced = self[:5]
            if isinstance(sliced, APIQuerySet):
                head: list[APIModel] = list(sliced)
            elif isinstance(sliced, list):
                head = sliced
            else:  # pragma: no cover
                head = [sliced]
        except Exception as exc:  # pragma: no cover - defensive
            return f"<APIQuerySet (unavailable: {exc!r})>"
        body = ", ".join(repr(o) for o in head)
        more = "..." if len(head) == 5 else ""
        return f"<APIQuerySet [{body}{more}]>"
