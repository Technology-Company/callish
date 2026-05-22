"""Adapter contract — the user-written layer between callish and an HTTP API."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AdapterProtocol(Protocol):
    """The structural contract every adapter must satisfy.

    Adapters are plain Python objects. They MAY also subclass :class:`BaseAdapter`
    for convenience, but it is not required — duck typing is sufficient.
    """

    def list(
        self,
        *,
        filters: Mapping[str, Any],
        ordering: Sequence[str],
        offset: int,
        limit: int | None,
    ) -> Sequence[Mapping[str, Any]]: ...

    def retrieve(self, pk: Any) -> Mapping[str, Any]: ...

    def create(self, data: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def update(self, pk: Any, data: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def delete(self, pk: Any) -> None: ...


class BaseAdapter:
    """Optional convenience base for adapters.

    Provides NotImplementedError stubs and a ``supported_lookups`` class attribute
    that the conformance suite uses to skip lookups the adapter doesn't claim.
    """

    #: Field-lookup suffixes (e.g. ``"in"``, ``"gte"``) the adapter promises to honour
    #: when passed in ``filters``. Equality (no suffix) is assumed always supported.
    supported_lookups: tuple[str, ...] = ("in", "gte", "lte", "contains", "icontains")

    def list(
        self,
        *,
        filters: Mapping[str, Any],
        ordering: Sequence[str],
        offset: int,
        limit: int | None,
    ) -> Sequence[Mapping[str, Any]]:
        raise NotImplementedError

    def retrieve(self, pk: Any) -> Mapping[str, Any]:
        raise NotImplementedError

    def create(self, data: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    def update(self, pk: Any, data: Mapping[str, Any]) -> Mapping[str, Any]:
        raise NotImplementedError

    def delete(self, pk: Any) -> None:
        raise NotImplementedError

    def count(self, *, filters: Mapping[str, Any]) -> int | None:
        """Optional. Return ``None`` to fall back to ``len(list(...))``."""
        return None


def resolve_adapter(spec: Any) -> Any:
    """Resolve an ``Meta.adapter`` declaration into an instance.

    Accepts:
      * An adapter instance — returned as-is.
      * An adapter class — instantiated with no args.
      * A dotted string ``"pkg.mod:ClassName"`` or ``"pkg.mod.ClassName"`` —
        imported then instantiated with no args.
    """
    if spec is None:
        raise ValueError("Meta.adapter is required on APIModel subclasses")

    if isinstance(spec, str):
        from importlib import import_module

        if ":" in spec:
            module_path, attr = spec.split(":", 1)
        elif "." in spec:
            module_path, attr = spec.rsplit(".", 1)
        else:
            raise ValueError(
                f"Adapter spec {spec!r} must be 'pkg.mod:Class' or 'pkg.mod.Class'"
            )
        module = import_module(module_path)
        spec = getattr(module, attr)

    if isinstance(spec, type):
        return spec()

    return spec
