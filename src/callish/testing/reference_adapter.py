"""In-memory adapter — reference implementation and self-test target."""

from __future__ import annotations

import copy
import itertools
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from ..exceptions import (
    AdapterValidationError,
    NotFound,
    RateLimited,
    Unauthorized,
    Upstream5xx,
)

#: Failure modes the adapter can be flipped into for M3 (error-path) tests.
FAILURE_MODES = frozenset(
    {"unauthorized", "ratelimited", "upstream5xx", "validation"}
)


class InMemoryAdapter:
    """Dict-backed adapter; pretends to be a remote REST service.

    Records are stored under ``pk_field`` (default ``"id"``). The store is local
    to the instance, so each test that wants isolation can construct a fresh
    adapter (or call :meth:`reset`).
    """

    #: Which lookups (suffixes on filter keys) we honour in :meth:`list`.
    supported_lookups: tuple[str, ...] = (
        "in",
        "gte",
        "lte",
        "gt",
        "lt",
        "contains",
        "icontains",
        "exact",
        "iexact",
        "startswith",
        "istartswith",
    )

    def __init__(
        self,
        records: Iterable[Mapping[str, Any]] | None = None,
        *,
        pk_field: str = "id",
        start_pk: int = 1,
    ) -> None:
        self.pk_field = pk_field
        self._counter = itertools.count(start_pk)
        self._store: dict[Any, dict[str, Any]] = {}
        self._failure_mode: str | None = None
        self._validation_errors: dict[str, list[str]] = {}
        # Call counts for tests that want to assert routing.
        self.calls: dict[str, int] = {
            "list": 0,
            "retrieve": 0,
            "create": 0,
            "update": 0,
            "delete": 0,
            "count": 0,
        }
        if records:
            self.seed(records)

    # ----- test helpers ---------------------------------------------------

    def reset(self) -> None:
        self._store.clear()
        self._counter = itertools.count(1)
        self._failure_mode = None
        self._validation_errors = {}
        for k in self.calls:
            self.calls[k] = 0

    def seed(self, records: Iterable[Mapping[str, Any]]) -> None:
        for record in records:
            data = dict(record)
            if self.pk_field not in data or data[self.pk_field] is None:
                data[self.pk_field] = next(self._counter)
            self._store[data[self.pk_field]] = data

    def set_failure_mode(
        self,
        mode: str | None,
        *,
        validation_errors: Mapping[str, Iterable[str]] | None = None,
    ) -> None:
        if mode is not None and mode not in FAILURE_MODES:
            raise ValueError(
                f"Unknown failure mode {mode!r}; expected one of {sorted(FAILURE_MODES)}"
            )
        self._failure_mode = mode
        if validation_errors:
            self._validation_errors = {
                k: list(v) for k, v in validation_errors.items()
            }

    # ----- adapter contract ----------------------------------------------

    def list(
        self,
        *,
        filters: Mapping[str, Any],
        ordering: Sequence[str],
        offset: int,
        limit: int | None,
    ) -> Sequence[Mapping[str, Any]]:
        self.calls["list"] += 1
        self._raise_failure()
        rows = [copy.deepcopy(r) for r in self._store.values()]
        rows = [r for r in rows if self._matches(r, filters)]
        rows = _sort_rows(rows, ordering)
        end = None if limit is None else offset + limit
        return rows[offset:end]

    def retrieve(self, pk: Any) -> Mapping[str, Any]:
        self.calls["retrieve"] += 1
        self._raise_failure()
        try:
            return copy.deepcopy(self._store[pk])
        except KeyError as exc:
            raise NotFound(f"{self.pk_field}={pk!r}") from exc

    def create(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls["create"] += 1
        self._raise_failure()
        record = {k: v for k, v in data.items() if v is not None or k == self.pk_field}
        # Drop None values for non-pk fields; preserve everything else.
        record = {k: data[k] for k in data}
        if self.pk_field not in record or record[self.pk_field] is None:
            record[self.pk_field] = next(self._counter)
        self._store[record[self.pk_field]] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def update(self, pk: Any, data: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls["update"] += 1
        self._raise_failure()
        if pk not in self._store:
            raise NotFound(f"{self.pk_field}={pk!r}")
        existing = self._store[pk]
        # Treat ``None`` as "don't change" — mirrors a typical PATCH/PUT API
        # where omitted values are left alone. Tests can verify partial updates.
        for k, v in data.items():
            if k == self.pk_field:
                continue
            existing[k] = v
        self._store[pk] = existing
        return copy.deepcopy(existing)

    def delete(self, pk: Any) -> None:
        self.calls["delete"] += 1
        self._raise_failure()
        if pk not in self._store:
            raise NotFound(f"{self.pk_field}={pk!r}")
        del self._store[pk]

    def count(self, *, filters: Mapping[str, Any]) -> int | None:
        self.calls["count"] += 1
        self._raise_failure()
        rows = [r for r in self._store.values() if self._matches(r, filters)]
        return len(rows)

    # ----- internals ------------------------------------------------------

    def _raise_failure(self) -> None:
        mode = self._failure_mode
        if mode is None:
            return
        if mode == "unauthorized":
            raise Unauthorized("authentication required")
        if mode == "ratelimited":
            raise RateLimited("rate limit exceeded", retry_after=1.0)
        if mode == "upstream5xx":
            raise Upstream5xx("upstream is broken", status=502)
        if mode == "validation":
            raise AdapterValidationError(
                "validation failed", errors=dict(self._validation_errors)
            )

    @staticmethod
    def _matches(record: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
        for key, expected in filters.items():
            if "__" in key:
                name, lookup = key.split("__", 1)
            else:
                name, lookup = key, "exact"
            value = record.get(name)
            if not _apply_lookup(value, lookup, expected):
                return False
        return True

def _sort_rows(
    rows: list[dict[str, Any]], ordering: Sequence[str]
) -> list[dict[str, Any]]:
    """Apply an ordering tuple to a list of records, Django-style.

    Moved to module scope so mypy doesn't confuse ``list`` (the builtin) with
    :meth:`InMemoryAdapter.list` when resolving annotations inside the class.
    """
    if not ordering:
        return rows

    def key(row: dict[str, Any]) -> tuple:
        parts: list[tuple[bool, Any]] = []
        for ord_spec in ordering:
            descending = ord_spec.startswith("-")
            field = ord_spec[1:] if descending else ord_spec
            value = row.get(field)
            # ``None`` last for asc, first for desc — matches Django default.
            parts.append((value is None, _ReverseWrapper(value) if descending else value))
        return tuple(parts)

    return sorted(rows, key=key)


def _apply_lookup(value: Any, lookup: str, expected: Any) -> bool:
    if lookup in ("exact",):
        return value == expected
    if lookup == "iexact":
        return str(value).lower() == str(expected).lower()
    if lookup == "in":
        return value in expected
    if lookup == "gte":
        return value is not None and value >= expected
    if lookup == "lte":
        return value is not None and value <= expected
    if lookup == "gt":
        return value is not None and value > expected
    if lookup == "lt":
        return value is not None and value < expected
    if lookup == "contains":
        return expected in (value or "")
    if lookup == "icontains":
        return str(expected).lower() in str(value or "").lower()
    if lookup == "startswith":
        return str(value or "").startswith(str(expected))
    if lookup == "istartswith":
        return str(value or "").lower().startswith(str(expected).lower())
    raise ValueError(f"InMemoryAdapter does not support lookup {lookup!r}")


class _ReverseWrapper:
    """Tiny helper to invert ordering for ``-fieldname`` keys.

    We can't just negate values (strings/dates aren't negatable), so wrap them
    and invert ``__lt__``.
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: _ReverseWrapper) -> bool:
        if self.value is None and other.value is None:
            return False
        if self.value is None:
            return False
        if other.value is None:
            return True
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _ReverseWrapper) and self.value == other.value
