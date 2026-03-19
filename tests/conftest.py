"""Shared pytest configuration for workflow-agent tests."""

from __future__ import annotations

import os
import shutil

import pytest


AUGGIE_AVAILABLE = shutil.which("auggie") is not None
CI_AUGGIE_ENABLED = os.environ.get("RUN_AUGGIE_TESTS") == "1"


def pytest_configure(config):
    config.addinivalue_line("markers", "auggie: tests requiring the auggie CLI")


def pytest_collection_modifyitems(config, items):
    if not AUGGIE_AVAILABLE:
        marker = pytest.mark.skip(reason="auggie CLI not available")
    elif os.environ.get("CI") and not CI_AUGGIE_ENABLED:
        marker = pytest.mark.skip(reason="auggie tests disabled in CI (set RUN_AUGGIE_TESTS=1)")
    else:
        return

    for item in items:
        if "auggie" in item.keywords:
            item.add_marker(marker)
