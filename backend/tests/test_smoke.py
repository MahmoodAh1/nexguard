"""Smoke test: the package imports and exposes its version."""

from __future__ import annotations

import nexguard


def test_package_imports_and_has_version() -> None:
    assert isinstance(nexguard.__version__, str)
    assert nexguard.__version__.count(".") >= 2
