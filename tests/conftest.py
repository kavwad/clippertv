"""Shared test configuration.

All tests are marked `prepush` by default (they're fast unit tests).
Tests that hit real APIs or are slow should be marked `integration` instead,
which excludes them from the prepush gate.
"""

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Auto-mark all tests as prepush unless they already have integration marker."""
    prepush = pytest.mark.prepush
    for item in items:
        if "integration" not in item.keywords:
            item.add_marker(prepush)
