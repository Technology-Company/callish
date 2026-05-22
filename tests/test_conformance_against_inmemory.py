"""Smoke test — run the shipping conformance suite against InMemoryAdapter.

If the bundled suite goes red against its own reference adapter, that's a
library bug. This file is a thin pytest invocation so the smoke is part of
the normal ``pytest`` run rather than something users have to remember to
trigger separately.
"""

from __future__ import annotations

import subprocess
import sys


def test_shipping_suite_runs_against_inmemory_adapter():
    """Spawn a subprocess that runs the conformance suite end-to-end.

    Subprocess isolation is intentional: the suite uses its own
    ``conform_adapter`` / ``conform_model`` fixtures from the pytest plugin,
    and we don't want the main test session's autouse adapter-reset fixture
    to interfere with it.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--pyargs",
            "callish.testing.suite",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Conformance suite failed against InMemoryAdapter:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
