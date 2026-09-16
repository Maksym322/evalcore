"""Smoke test: the package imports and exposes a version string."""

import evalcore


def test_package_exposes_version() -> None:
    assert isinstance(evalcore.__version__, str)
    assert evalcore.__version__
