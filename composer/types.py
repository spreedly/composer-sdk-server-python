"""Type definitions for the Composer SDK."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from composer.constants import (
    DEFAULT_API_URL,
    DEFAULT_REQUEST_TIMEOUT_MS,
    ApiVersion,
    VerificationOutcome,
    VerificationStatus,
)
from composer.logger import ComposerLogLevel

# Backward compatibility aliases
ComposerApiVersion = ApiVersion
DodgeballApiVersion = ApiVersion


@dataclass
class ComposerConfig:
    """Configuration for the Composer SDK client."""

    api_version: str = ApiVersion.V1.value
    api_url: str = DEFAULT_API_URL
    log_level: str = ComposerLogLevel.INFO
    is_enabled: bool = True
    request_timeout_ms: int = DEFAULT_REQUEST_TIMEOUT_MS


# Backward compatibility alias
DodgeballConfig = ComposerConfig


@dataclass
class CheckpointEvent:
    """Event data for a checkpoint submission."""

    ip: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrackEvent:
    """Event data for tracking."""

    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    event_time: Optional[int] = None


@dataclass
class CheckpointResponseOptions:
    """Options for customizing checkpoint response behavior."""

    sync: bool = False
    timeout: Optional[int] = None


@dataclass
class ApiError:
    """Error information from the API."""

    code: int
    message: str


@dataclass
class Verification:
    """Verification information from a checkpoint response."""

    id: str
    status: str
    outcome: str
    status_code: Optional[int] = None
    next_steps: List[Any] = field(default_factory=list)
    step_data: Optional[Dict[str, Any]] = None


@dataclass
class CheckpointResponse:
    """Response from a checkpoint submission."""

    success: bool
    errors: List[ApiError]
    version: str
    verification: Verification
    is_timed_out: bool = False

    def is_allowed(self) -> bool:
        """Check if the verification was approved and complete."""
        return (
            self.success
            and self.verification.outcome == VerificationOutcome.APPROVED.value
            and self.verification.status == VerificationStatus.COMPLETE.value
        )

    def is_denied(self) -> bool:
        """Check if the verification was denied."""
        return self.success and self.verification.outcome == VerificationOutcome.DENIED.value

    def is_running_check(self) -> bool:
        """Check if the verification is still running with no verdict yet."""
        return (
            self.success
            and self.verification.status
            in (VerificationStatus.PENDING.value, VerificationStatus.BLOCKED.value)
            and self.verification.outcome == VerificationOutcome.PENDING.value
        )

    def is_undecided(self) -> bool:
        """Check if the verification is complete but its outcome is still pending."""
        return (
            self.success
            and self.verification.status == VerificationStatus.COMPLETE.value
            and self.verification.outcome == VerificationOutcome.PENDING.value
        )

    def has_error(self) -> bool:
        """Check if the verification encountered an error."""
        return not self.success or self.verification.outcome == VerificationOutcome.ERROR.value

    def is_timeout(self) -> bool:
        """Check if the verification timed out."""
        return self.is_timed_out
