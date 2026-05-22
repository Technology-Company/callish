"""``APIModelForm`` — a ``ModelForm`` that talks to adapters instead of the DB.

This subclasses Django's ``ModelForm`` directly: ``ModelFormMetaclass`` only
needs ``model._meta`` to expose the surface ``fields_for_model`` walks. Our
``_meta`` shim does. ``_post_clean`` is overridden to skip DB-level validation,
and ``save`` is overridden to dispatch to ``adapter.create/update``.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import construct_instance

from .exceptions import AdapterValidationError


class APIModelForm(forms.ModelForm):
    """ModelForm replacement that round-trips through an adapter."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def _post_clean(self) -> None:
        """Skip the DB-constraint pass; keep the field-level construct_instance."""
        opts = self._meta
        try:
            self.instance = construct_instance(
                self,
                self.instance,  # type: ignore[has-type]
                opts.fields,
                opts.exclude,
            )
        except ValidationError as e:
            self._update_errors(e)
        # Intentionally NOT calling self.instance.full_clean() — the adapter is
        # the source of truth for upstream validation (and would raise
        # AdapterValidationError on failure during save()).

    def save(self, commit: bool = True) -> Any:
        """Send the instance through the adapter.

        Adapter errors propagate. :class:`AdapterValidationError` is translated
        into a form-level :class:`~django.core.exceptions.ValidationError` so
        downstream code can display per-field messages.
        """
        if not commit:
            # Caller wants to inspect/mutate the instance before persisting.
            return self.instance

        try:
            self.instance.save()
        except AdapterValidationError as exc:
            self._update_errors(ValidationError(exc.errors or {"__all__": [str(exc)]}))
            raise
        return self.instance
