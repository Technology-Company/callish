"""Manager for API-backed models — Django ``.objects`` analogue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .queryset import APIQuerySet

if TYPE_CHECKING:
    from .models import APIModel


class APIManager:
    """Minimal manager: spawns querysets and proxies the common terminal methods."""

    # Django generic views look at this attribute (``model._default_manager``).
    use_in_migrations = False

    def __init__(self) -> None:
        self.model: type[APIModel] | None = None
        self.name: str = "objects"

    def contribute_to_class(self, model: type[APIModel], name: str) -> None:
        self.model = model
        self.name = name
        setattr(model, name, self)
        # Django generic views look for ``_default_manager`` and ``_meta.base_manager``.
        if getattr(model, "_default_manager", None) is None:
            model._default_manager = self

    # ----- queryset spawners ----------------------------------------------

    def get_queryset(self) -> APIQuerySet:
        if self.model is None:
            raise RuntimeError("APIManager is not attached to a model.")
        return APIQuerySet(self.model)

    def all(self) -> APIQuerySet:
        return self.get_queryset()

    def none(self) -> APIQuerySet:
        return self.get_queryset().none()

    def filter(self, **kwargs: Any) -> APIQuerySet:
        return self.get_queryset().filter(**kwargs)

    def exclude(self, **kwargs: Any) -> APIQuerySet:
        return self.get_queryset().exclude(**kwargs)

    def order_by(self, *fields: str) -> APIQuerySet:
        return self.get_queryset().order_by(*fields)

    def get(self, **kwargs: Any) -> APIModel:
        return self.get_queryset().get(**kwargs)

    def first(self) -> APIModel | None:
        return self.get_queryset().first()

    def last(self) -> APIModel | None:
        return self.get_queryset().last()

    def exists(self) -> bool:
        return self.get_queryset().exists()

    def count(self) -> int:
        return self.get_queryset().count()

    # ----- write helpers ---------------------------------------------------

    def create(self, **kwargs: Any) -> APIModel:
        assert self.model is not None
        instance = self.model(**kwargs)
        instance.save()
        return instance
