"""``APIModel`` — base class and metaclass for API-backed Django-shaped models."""

from __future__ import annotations

from typing import Any, ClassVar

from django.db.models import Field

from ._meta import Options
from .adapter import resolve_adapter
from .manager import APIManager


class APIModelDoesNotExist(Exception):
    """Default ``DoesNotExist`` analogue (each subclass gets its own)."""


def _build_does_not_exist(name: str) -> type[Exception]:
    return type(f"{name}.DoesNotExist", (APIModelDoesNotExist,), {})


class APIModelMetaclass(type):
    """Collects field declarations, builds the ``_meta`` shim, attaches manager."""

    def __new__(mcs, name, bases, attrs):
        # The base class itself: define and bail out — no meta processing.
        parents = [b for b in bases if isinstance(b, APIModelMetaclass)]
        if not parents:
            return super().__new__(mcs, name, bases, attrs)

        # Collect field declarations (ordered by Django's creation_counter).
        declared_fields: dict[str, Field] = {}
        for attr_name, value in list(attrs.items()):
            if isinstance(value, Field):
                declared_fields[attr_name] = value
                attrs.pop(attr_name)

        # Inherit fields from base APIModel subclasses (most-base-first, no overrides
        # — child decls always win because they're already in declared_fields).
        for base in bases:
            base_meta = getattr(base, "_meta", None)
            if base_meta is None or not getattr(base_meta, "callish_shim", False):
                continue
            for f in base_meta.concrete_fields:
                declared_fields.setdefault(f.name, f)

        # Sort by Django's creation_counter so declaration order is preserved.
        ordered = sorted(declared_fields.items(), key=lambda kv: kv[1].creation_counter)

        # Wire field name/attname BEFORE building _meta — fields_for_model walks
        # concrete_fields and pulls .name off each.
        pk_field: Field | None = None
        fields: list[Field] = []
        for field_name, field in ordered:
            field.set_attributes_from_name(field_name)
            # Field.model is referenced by some Django code paths during admin/forms;
            # we'll set it after we have the class.
            fields.append(field)
            if getattr(field, "primary_key", False):
                if pk_field is not None:
                    raise TypeError(
                        f"{name} declares multiple primary keys: "
                        f"{pk_field.name} and {field.name}"
                    )
                pk_field = field

        if pk_field is None and fields:
            # Default to an implicit auto-incrementing 'id' field if none declared.
            from django.db.models import AutoField

            pk_field = AutoField(primary_key=True, auto_created=True)
            pk_field.set_attributes_from_name("id")
            fields.insert(0, pk_field)

        # Read Meta options.
        meta_opts = attrs.pop("Meta", None)
        adapter_spec = getattr(meta_opts, "adapter", None) if meta_opts else None
        app_label = (
            getattr(meta_opts, "app_label", None) if meta_opts else None
        ) or "callish"
        verbose_name = getattr(meta_opts, "verbose_name", None) if meta_opts else None
        verbose_name_plural = (
            getattr(meta_opts, "verbose_name_plural", None) if meta_opts else None
        )

        # Build the new class first so Field.model can point at it.
        new_class = super().__new__(mcs, name, bases, attrs)

        # If this subclass is abstract (no adapter), skip wiring.
        is_abstract = (
            getattr(meta_opts, "abstract", False) if meta_opts is not None else False
        )

        new_class._meta = Options(
            model=new_class,
            fields=fields,
            pk_field=pk_field,
            app_label=app_label,
            object_name=name,
            verbose_name=verbose_name,
            verbose_name_plural=verbose_name_plural,
        )
        # Back-fill ``field.model`` so admin / forms inspection works.
        for field in fields:
            field.model = new_class

        # DoesNotExist + MultipleObjectsReturned analogues, Django-style.
        new_class.DoesNotExist = _build_does_not_exist(name)
        from django.core.exceptions import MultipleObjectsReturned as _MOR

        new_class.MultipleObjectsReturned = type(
            f"{name}.MultipleObjectsReturned", (_MOR,), {}
        )

        if not is_abstract:
            if adapter_spec is None:
                raise TypeError(
                    f"{name}.Meta.adapter is required (got None). Set it to an "
                    "adapter instance, class, or 'pkg.mod:Class' import string."
                )
            new_class._callish_adapter = resolve_adapter(adapter_spec)
            # Attach manager.
            manager = APIManager()
            manager.contribute_to_class(new_class, "objects")
            new_class._default_manager = manager
            new_class._meta.base_manager = manager  # generic-view friendly

        return new_class


class APIModel(metaclass=APIModelMetaclass):
    """Base class for API-backed model declarations.

    Subclasses declare fields like ``CharField``, ``IntegerField`` and a
    ``Meta`` with an ``adapter`` attribute pointing at an adapter instance,
    class, or import string.
    """

    # Class-level placeholders — the metaclass replaces these on real subclasses.
    objects: ClassVar[APIManager]
    _default_manager: ClassVar[APIManager]
    _callish_adapter: ClassVar[Any]
    _meta: ClassVar[Options]
    DoesNotExist: ClassVar[type[Exception]] = APIModelDoesNotExist
    MultipleObjectsReturned: ClassVar[type[Exception]]

    # ----- construction ----------------------------------------------------

    def __init__(self, **kwargs: Any) -> None:
        meta = type(self)._meta
        # Initialise all known fields to their default (or None).
        for field in meta.concrete_fields:
            if field.name in kwargs:
                value = kwargs.pop(field.name)
            elif field.has_default():
                value = field.get_default()
            else:
                value = None
            setattr(self, field.name, value)
        if kwargs:
            unknown = ", ".join(sorted(kwargs))
            raise TypeError(f"Unknown field(s) for {type(self).__name__}: {unknown}")

    @classmethod
    def _from_record(cls, record: dict[str, Any]) -> APIModel:
        """Build an instance from an adapter-returned dict.

        Unknown keys are stashed on the instance via ``setattr`` so adapters
        that return extra metadata don't get silently dropped — callers can
        still access them, they just won't be considered model fields.
        """
        meta = cls._meta
        known = {f.name: record.get(f.name) for f in meta.concrete_fields if f.name in record}
        instance = cls(**known)
        for key, value in record.items():
            if key not in known:
                setattr(instance, key, value)
        return instance

    # ----- pk + persistence helpers ---------------------------------------

    @property
    def pk(self) -> Any:
        return getattr(self, type(self)._meta.pk.name, None)

    @pk.setter
    def pk(self, value: Any) -> None:
        setattr(self, type(self)._meta.pk.name, value)

    def _as_payload(self, *, include_pk: bool = False) -> dict[str, Any]:
        meta = type(self)._meta
        data: dict[str, Any] = {}
        for field in meta.concrete_fields:
            if not include_pk and field is meta.pk:
                continue
            data[field.name] = getattr(self, field.name, None)
        return data

    def _refresh_from_dict(self, record: dict[str, Any]) -> None:
        meta = type(self)._meta
        for field in meta.concrete_fields:
            if field.name in record:
                setattr(self, field.name, record[field.name])

    def save(self) -> None:
        adapter = type(self)._callish_adapter
        if self.pk is None:
            record = adapter.create(self._as_payload(include_pk=False))
        else:
            record = adapter.update(self.pk, self._as_payload(include_pk=False))
        self._refresh_from_dict(dict(record))

    def delete(self) -> None:
        if self.pk is None:
            raise ValueError(
                f"{type(self).__name__} instance has no pk; refusing to delete."
            )
        type(self)._callish_adapter.delete(self.pk)
        self.pk = None

    def refresh_from_db(self) -> None:
        if self.pk is None:
            raise ValueError(
                f"{type(self).__name__} instance has no pk; cannot refresh."
            )
        record = type(self)._callish_adapter.retrieve(self.pk)
        self._refresh_from_dict(dict(record))

    # ----- Python protocol -------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return NotImplemented
        if self.pk is None or other.pk is None:
            return self is other
        return self.pk == other.pk

    def __hash__(self) -> int:
        if self.pk is None:
            return id(self)
        return hash((type(self).__name__, self.pk))

    def __repr__(self) -> str:
        return f"<{type(self).__name__}: pk={self.pk!r}>"
