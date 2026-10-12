"""Logging functionality for the Composer SDK."""

import json
import sys
from datetime import datetime, timezone
from enum import IntEnum
from typing import Any, Dict, Optional


class ComposerLogLevel(str):
    """Log levels for the Composer SDK."""

    TRACE = "TRACE"
    INFO = "INFO"
    ERROR = "ERROR"
    NONE = "NONE"


# Backward compatibility alias
DodgeballLogLevel = ComposerLogLevel


class Severity(IntEnum):
    """Internal severity levels for filtering."""

    TRACE = 0
    INFO = 1
    ERROR = 2
    NONE = 3


class LogEntry:
    """Represents a log entry with message, severity, and optional metadata."""

    def __init__(self, message: str, severity: Severity):
        self.message = message
        self.severity = severity
        self.parameters: Dict[str, Any] = {}
        self.error: Optional[Exception] = None
        self.date = datetime.now(timezone.utc)

    def set_parameter(self, key: str, value: Any) -> "LogEntry":
        """Add a parameter to the log entry."""
        self.parameters[key] = value
        return self

    def set_parameters(self, parameters: Dict[str, Any]) -> "LogEntry":
        """Set multiple parameters at once."""
        self.parameters.update(parameters)
        return self

    def set_severity(self, severity: Severity) -> "LogEntry":
        """Set the severity level."""
        self.severity = severity
        return self

    def set_error(self, error: Exception) -> "LogEntry":
        """Attach an exception to the log entry."""
        self.error = error
        return self

    def log(self) -> None:
        """Write the log entry to stdout if it passes the filter level."""
        if self.severity < Logger.filter_level:
            return

        output: Dict[str, Any] = {
            "message": self.message,
            "severity": _severity_to_string(self.severity),
            "date": self.date.isoformat() + "Z",
        }

        if self.parameters:
            output["parameters"] = self.parameters

        if self.error:
            output["error"] = Logger.format_error(self.error)

        print(json.dumps(output, separators=(",", ":")), file=sys.stdout)


class Logger:
    """Static logger for the Composer SDK."""

    filter_level: Severity = Severity.INFO

    @staticmethod
    def is_trace_enabled() -> bool:
        """Report whether a trace entry would be written.

        Callers check this before assembling an expensive trace message, because the
        message is built before log() gets a chance to discard it.
        """
        return Severity.TRACE >= Logger.filter_level

    @staticmethod
    def info(message: str, parameters: Optional[Dict[str, Any]] = None) -> LogEntry:
        """Create an info-level log entry."""
        entry = LogEntry(message, Severity.INFO)
        if parameters:
            entry.set_parameters(parameters)
        return entry

    @staticmethod
    def trace(message: str, parameters: Optional[Dict[str, Any]] = None) -> LogEntry:
        """Create a trace-level log entry."""
        entry = LogEntry(message, Severity.TRACE)
        if parameters:
            entry.set_parameters(parameters)
        return entry

    @staticmethod
    def error(message: str, error: Optional[Exception] = None) -> LogEntry:
        """Create an error-level log entry."""
        entry = LogEntry(message, Severity.ERROR)
        if error:
            entry.set_error(error)
        return entry

    @staticmethod
    def format_error(error: Optional[Exception]) -> str:
        """Format an exception as a JSON string."""
        if not error:
            return ""

        import traceback

        error_data = {
            "message": str(error),
            "name": type(error).__name__,
        }

        # Include stack trace if available
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        if tb:
            error_data["stack"] = "".join(tb)

        return json.dumps(error_data)

    @staticmethod
    def log_level_to_severity(log_level: str) -> Severity:
        """Convert a log level string to a Severity enum."""
        mapping = {
            ComposerLogLevel.TRACE: Severity.TRACE,
            ComposerLogLevel.INFO: Severity.INFO,
            ComposerLogLevel.ERROR: Severity.ERROR,
            ComposerLogLevel.NONE: Severity.NONE,
        }
        return mapping.get(log_level, Severity.INFO)


def _severity_to_string(severity: Severity) -> str:
    """Convert a Severity enum to a string."""
    mapping = {
        Severity.TRACE: "TRACE",
        Severity.INFO: "INFO",
        Severity.ERROR: "ERROR",
        Severity.NONE: "NONE",
    }
    return mapping.get(severity, "UNKNOWN")
