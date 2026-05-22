"""Django app config for callish.

Intentionally inert: no signals, no monkey-patching, no admin-site mutations.
This keeps callish coexistence-safe with Wagtail and any other framework that
expects to own its corners of Django.
"""

from __future__ import annotations

from django.apps import AppConfig


class CallishConfig(AppConfig):
    name = "callish"
    label = "callish"
    verbose_name = "callish"
    # Required for Django to instantiate AppConfig — we have no real models.
    default_auto_field = "django.db.models.BigAutoField"
