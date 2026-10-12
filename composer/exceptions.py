"""Exception classes for the Composer SDK."""

from typing import Any, List, Optional


class ComposerException(Exception):
    """Base exception for all Composer SDK errors."""

    def __init__(self, message: str, inner_exception: Optional[Exception] = None):
        super().__init__(message)
        self.inner_exception = inner_exception


class ComposerMissingParameterError(ComposerException):
    """Raised when a required parameter is missing."""

    def __init__(self, parameter_name: str):
        message = f"Missing required parameter: {parameter_name}"
        super().__init__(message)
        self.parameter_name = parameter_name


class ComposerMissingConfigError(ComposerException):
    """Raised when required configuration is missing."""

    def __init__(self, config_name: str, value: Any):
        message = f"Missing required config: {config_name}"
        super().__init__(message)
        self.config_name = config_name
        self.value = value


class ComposerInvalidConfigError(ComposerException):
    """Raised when configuration has an invalid value."""

    def __init__(self, config_name: str, value: Any, allowed_values: List[str]):
        allowed = ", ".join(allowed_values)
        message = f"Invalid config value for {config_name}: {value}. Allowed values: {allowed}"
        super().__init__(message)
        self.config_name = config_name
        self.value = value
        self.allowed_values = allowed_values
