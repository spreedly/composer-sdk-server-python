"""Tests for logger module."""

import io
import json
from contextlib import redirect_stdout

from composer.logger import (
    ComposerLogLevel,
    DodgeballLogLevel,
    LogEntry,
    Logger,
    Severity,
)


def test_severity_values():
    """Test Severity enum values."""
    assert Severity.TRACE == 0
    assert Severity.INFO == 1
    assert Severity.ERROR == 2
    assert Severity.NONE == 3


def test_log_entry_creation():
    """Test LogEntry creation."""
    entry = LogEntry("Test message", Severity.INFO)
    assert entry.message == "Test message"
    assert entry.severity == Severity.INFO
    assert entry.parameters == {}
    assert entry.error is None
    assert entry.date is not None


def test_log_entry_set_parameter():
    """Test LogEntry.set_parameter method."""
    entry = LogEntry("Test", Severity.INFO)
    result = entry.set_parameter("key", "value")
    assert result is entry  # Should return self for chaining
    assert entry.parameters["key"] == "value"


def test_log_entry_set_parameters():
    """Test LogEntry.set_parameters method."""
    entry = LogEntry("Test", Severity.INFO)
    params = {"key1": "value1", "key2": 42}
    result = entry.set_parameters(params)
    assert result is entry
    assert entry.parameters["key1"] == "value1"
    assert entry.parameters["key2"] == 42


def test_log_entry_set_severity():
    """Test LogEntry.set_severity method."""
    entry = LogEntry("Test", Severity.INFO)
    result = entry.set_severity(Severity.ERROR)
    assert result is entry
    assert entry.severity == Severity.ERROR


def test_log_entry_set_error():
    """Test LogEntry.set_error method."""
    entry = LogEntry("Test", Severity.ERROR)
    exc = ValueError("Test error")
    result = entry.set_error(exc)
    assert result is entry
    assert entry.error is exc


def test_log_entry_log_with_allowed_severity():
    """Test LogEntry.log outputs when severity is allowed."""
    Logger.filter_level = Severity.TRACE
    entry = LogEntry("Test message", Severity.INFO)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        entry.log()

    output = buffer.getvalue()
    assert "Test message" in output
    assert '"severity":"INFO"' in output


def test_log_entry_log_with_filtered_severity():
    """Test LogEntry.log doesn't output when severity is filtered."""
    Logger.filter_level = Severity.ERROR
    entry = LogEntry("Test message", Severity.INFO)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        entry.log()

    output = buffer.getvalue()
    assert output == ""


def test_log_entry_log_with_parameters():
    """Test LogEntry.log includes parameters."""
    Logger.filter_level = Severity.TRACE
    entry = LogEntry("Test", Severity.INFO).set_parameter("key", "value")

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        entry.log()

    output = buffer.getvalue()
    data = json.loads(output.strip())
    assert data["parameters"]["key"] == "value"


def test_log_entry_log_with_error():
    """Test LogEntry.log includes formatted error."""
    Logger.filter_level = Severity.TRACE
    exc = ValueError("Test error")
    entry = LogEntry("Error occurred", Severity.ERROR).set_error(exc)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        entry.log()

    output = buffer.getvalue()
    assert "Test error" in output
    assert '"error"' in output


def test_logger_info():
    """Test Logger.info creates INFO entry."""
    entry = Logger.info("Info message")
    assert entry.message == "Info message"
    assert entry.severity == Severity.INFO


def test_logger_info_with_parameters():
    """Test Logger.info with parameters."""
    params = {"key": "value"}
    entry = Logger.info("Info message", params)
    assert entry.message == "Info message"
    assert entry.parameters["key"] == "value"


def test_logger_trace():
    """Test Logger.trace creates TRACE entry."""
    entry = Logger.trace("Trace message")
    assert entry.message == "Trace message"
    assert entry.severity == Severity.TRACE


def test_logger_trace_with_parameters():
    """Test Logger.trace with parameters."""
    params = {"trace": "data"}
    entry = Logger.trace("Trace message", params)
    assert entry.message == "Trace message"
    assert entry.parameters["trace"] == "data"


def test_logger_error():
    """Test Logger.error creates ERROR entry."""
    entry = Logger.error("Error message")
    assert entry.message == "Error message"
    assert entry.severity == Severity.ERROR
    assert entry.error is None


def test_logger_error_with_exception():
    """Test Logger.error with exception."""
    exc = ValueError("Test error")
    entry = Logger.error("Error message", exc)
    assert entry.message == "Error message"
    assert entry.error is exc


def test_logger_format_error():
    """Test Logger.format_error with exception."""
    exc = ValueError("Test error")
    result = Logger.format_error(exc)
    data = json.loads(result)
    assert data["message"] == "Test error"
    assert data["name"] == "ValueError"
    assert "stack" in data


def test_logger_format_error_with_none():
    """Test Logger.format_error with None."""
    result = Logger.format_error(None)
    assert result == ""


def test_logger_format_error_with_stack_trace():
    """Test Logger.format_error includes stack trace."""
    try:
        raise ValueError("Error with stack")
    except ValueError as exc:
        result = Logger.format_error(exc)
        data = json.loads(result)
        assert "stack" in data
        assert "Error with stack" in data["message"]


def test_logger_log_level_to_severity():
    """Test Logger.log_level_to_severity conversion."""
    assert Logger.log_level_to_severity(ComposerLogLevel.TRACE) == Severity.TRACE
    assert Logger.log_level_to_severity(ComposerLogLevel.INFO) == Severity.INFO
    assert Logger.log_level_to_severity(ComposerLogLevel.ERROR) == Severity.ERROR
    assert Logger.log_level_to_severity(ComposerLogLevel.NONE) == Severity.NONE


def test_logger_log_level_to_severity_invalid():
    """Test Logger.log_level_to_severity with invalid value defaults to INFO."""
    result = Logger.log_level_to_severity("INVALID")
    assert result == Severity.INFO


def test_dodgeball_log_level_backward_compat():
    """Test DodgeballLogLevel is an alias for ComposerLogLevel."""
    assert DodgeballLogLevel.TRACE == ComposerLogLevel.TRACE
    assert DodgeballLogLevel.INFO == ComposerLogLevel.INFO
    assert DodgeballLogLevel.ERROR == ComposerLogLevel.ERROR
    assert DodgeballLogLevel.NONE == ComposerLogLevel.NONE
