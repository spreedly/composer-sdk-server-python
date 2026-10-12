"""Test configuration and fixtures."""

import pytest

from composer.logger import Logger, Severity


@pytest.fixture(autouse=True)
def reset_logger():
    """Reset logger filter level after each test."""
    yield
    Logger.filter_level = Severity.NONE
