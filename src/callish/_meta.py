"""``_meta`` shim — exposes the surface Django introspects on real models.

Django's ``fields_for_model``, ``ModelForm``, generic class-based views and
URL reverse helpers all reach into ``model._meta`` for things like
``concrete_fields``, ``get_field``, ``app_label``, ``model_name``,
``verbose_name`` etc. This shim provides exactly those — and no more.

Anything Django reaches for that isn't here either lives outside callish's
v1 scope (relations, indexes, constraints, db_table) or signals a bug.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django.core.exceptions import FieldDoesNotExist
from django.db.models import Field

if TYPE_CHECKING:
    from .models import APIModel


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def _humanize(name: str) -> str:
    return _CAMEL_RE.sub(" ", name).strip().lower()


class Options:
    """Drop-in for ``django.db.models.options.Options`` — minimum viable surface."""

    # Marker so external code can tell us apart from a real Options.
    callish_shim = True

    # Real Django Options uses these to opt out of DB/admin behaviour we never want.
    proxy = False
    abstract = False
    swapped = False
    auto_created = False
    managed = False  # we have no DB table
    is_composite_pk = False  # Django 5.2+ admin compatibility

    # Empty collections that Django iterates blindly.
    many_to_many: list[Field] = []
    private_fields: list[Field] = []
    parents: dict[Any, Any] = {}
    local_many_to_many: list[Field] = []

    # Admin / changelist hint — not supported for v1.
    default_permissions: tuple[str, ...] = ()
    permissions: tuple[Any, ...] = ()

    def __init__(
        self,
        *,
        model: type[APIModel],
        fields: Iterable[Field],
        pk_field: Field,
        app_label: str,
        object_name: str,
        verbose_name: str | None = None,
        verbose_name_plural: str | None = None,
    ) -> None:
        self.model = model
        self.concrete_fields: list[Field] = list(fields)
        self.local_fields: list[Field] = list(self.concrete_fields)
        self.local_concrete_fields: list[Field] = list(self.concrete_fields)
        self.pk: Field = pk_field

        self.app_label = app_label
        self.object_name = object_name
        self.model_name = object_name.lower()
        self.verbose_name = verbose_name or _humanize(object_name)
        self.verbose_name_plural = verbose_name_plural or f"{self.verbose_name}s"

        # Build a name -> field map for fast lookup.
        self._field_map: dict[str, Field] = {f.name: f for f in self.concrete_fields}

    # ----- Django Options surface -----------------------------------------

    @property
    def fields(self) -> tuple[Field, ...]:
        return tuple(self.concrete_fields)

    @property
    def label(self) -> str:
        return f"{self.app_label}.{self.object_name}"

    @property
    def label_lower(self) -> str:
        return f"{self.app_label}.{self.model_name}"

    def get_field(self, field_name: str) -> Field:
        if field_name == "pk":
            return self.pk
        try:
            return self._field_map[field_name]
        except KeyError as exc:
            raise FieldDoesNotExist(
                f"{self.object_name} has no field named {field_name!r}"
            ) from exc

    def get_fields(
        self, include_parents: bool = True, include_hidden: bool = False
    ) -> tuple[Field, ...]:
        return self.fields

    # Django sometimes calls this to canonicalise the verbose name with case.
    @property
    def verbose_name_raw(self) -> str:
        return str(self.verbose_name)

    def __repr__(self) -> str:
        return f"<callish Options for {self.label}>"
