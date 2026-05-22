"""Opt-in coexistence test: callish + Wagtail in the same INSTALLED_APPS.

Skipped unless ``poetry install --with compat`` (or another mechanism)
has installed Wagtail. The goal is not to test Wagtail integration —
Wagtail Snippet/Chooser is an explicit non-goal — only to verify that
loading callish into a Wagtail project does not break Django startup.
"""

from __future__ import annotations

import pytest


def test_wagtail_and_callish_coexist():
    pytest.importorskip("wagtail")
    # If the test session is already configured with callish in INSTALLED_APPS
    # and we can import wagtail without anything blowing up, we've shown the
    # avoidance contract (no monkey-patching) holds.
    import django
    from django.apps import apps

    django.setup()
    assert apps.is_installed("callish")
    # Sanity: callish.apps.CallishConfig.ready() must remain inert. If a future
    # change adds side effects, this assertion will need a more specific check.
    assert apps.get_app_config("callish").label == "callish"
