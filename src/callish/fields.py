"""Field wrappers — thin shims around ``django.db.models.fields.*`` instances.

These are declared on :class:`callish.APIModel` subclasses but never attached
to a real DB table. The metaclass calls :meth:`set_attributes_from_name` on
each so ``field.name`` / ``field.attname`` are populated, which is enough for
Django's ``fields_for_model`` to introspect them and produce form fields.
"""

from __future__ import annotations

from django.db import models as dj_models

# Re-export Django field classes verbatim. We intentionally do not subclass:
# subclasses would inherit ``contribute_to_class`` behaviour that assumes a real
# Model, and the metaclass already handles attachment.
CharField = dj_models.CharField
TextField = dj_models.TextField
IntegerField = dj_models.IntegerField
BigIntegerField = dj_models.BigIntegerField
SmallIntegerField = dj_models.SmallIntegerField
PositiveIntegerField = dj_models.PositiveIntegerField
FloatField = dj_models.FloatField
DecimalField = dj_models.DecimalField
BooleanField = dj_models.BooleanField
DateField = dj_models.DateField
DateTimeField = dj_models.DateTimeField
TimeField = dj_models.TimeField
EmailField = dj_models.EmailField
URLField = dj_models.URLField
SlugField = dj_models.SlugField
UUIDField = dj_models.UUIDField
JSONField = dj_models.JSONField
BinaryField = dj_models.BinaryField

__all__ = [
    "BigIntegerField",
    "BinaryField",
    "BooleanField",
    "CharField",
    "DateField",
    "DateTimeField",
    "DecimalField",
    "EmailField",
    "FloatField",
    "IntegerField",
    "JSONField",
    "PositiveIntegerField",
    "SlugField",
    "SmallIntegerField",
    "TextField",
    "TimeField",
    "URLField",
    "UUIDField",
]
