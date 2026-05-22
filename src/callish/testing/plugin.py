"""pytest plugin — auto-registered via the ``pytest11`` entry point.

Provides fixtures the conformance suite expects (``conform_model``) and a
``--callish-skip-m3`` CLI flag for incremental adoption.
"""

from __future__ import annotations

import pytest

from .helpers import make_invoice_model
from .reference_adapter import InMemoryAdapter


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("callish")
    group.addoption(
        "--callish-skip-m3",
        action="store_true",
        default=False,
        help="Skip M3 (error/timeout) conformance tests. Useful while M1+M2 are still red.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "callish_milestone(name): mark a conformance test as belonging to a milestone (m1/m2/m3).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--callish-skip-m3"):
        return
    skip_m3 = pytest.mark.skip(reason="--callish-skip-m3 supplied")
    for item in items:
        marker = item.get_closest_marker("callish_milestone")
        if marker and marker.args and marker.args[0] == "m3":
            item.add_marker(skip_m3)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conform_adapter():
    """Default adapter for the shipping conformance suite.

    Downstream users override this in their own conftest to point at their
    real adapter; the library itself uses it to dogfood ``InMemoryAdapter``.
    """
    yield InMemoryAdapter()


@pytest.fixture
def conform_model(conform_adapter):
    """Auto-built ``Invoice``-shaped APIModel pointed at ``conform_adapter``."""
    return make_invoice_model(conform_adapter)
