"""Tests for exceptions module."""

from composer.exceptions import (
    ComposerException,
    ComposerInvalidConfigError,
    ComposerMissingConfigError,
    ComposerMissingParameterError,
)


def test_composer_exception():
    """Test base ComposerException."""
    exc = ComposerException("Test error")
    assert str(exc) == "Test error"
    assert exc.inner_exception is None


def test_composer_exception_with_inner():
    """Test ComposerException with inner exception."""
    inner = ValueError("Inner error")
    exc = ComposerException("Outer error", inner)
    assert str(exc) == "Outer error"
    assert exc.inner_exception == inner


def test_missing_parameter_error():
    """Test ComposerMissingParameterError."""
    exc = ComposerMissingParameterError("userId")
    assert "Missing required parameter: userId" in str(exc)
    assert exc.parameter_name == "userId"
    assert not hasattr(exc, "value")


def test_missing_config_error():
    """Test ComposerMissingConfigError."""
    exc = ComposerMissingConfigError("secretKey", "")
    assert "Missing required config: secretKey" in str(exc)
    assert exc.config_name == "secretKey"
    assert exc.value == ""


def test_invalid_config_error():
    """Test ComposerInvalidConfigError."""
    exc = ComposerInvalidConfigError("apiVersion", "v2", ["v1"])
    assert "Invalid config value for apiVersion: v2" in str(exc)
    assert "Allowed values: v1" in str(exc)
    assert exc.config_name == "apiVersion"
    assert exc.value == "v2"
    assert exc.allowed_values == ["v1"]
