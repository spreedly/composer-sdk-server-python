"""Constants used throughout the Composer SDK."""

from enum import Enum


class ApiVersion(str, Enum):
    """API version enum."""

    V1 = "v1"


class VerificationStatus(str, Enum):
    """Status of a verification workflow."""

    PENDING = "PENDING"  # In process on the server
    BLOCKED = "BLOCKED"  # Waiting on some action, for example MFA
    COMPLETE = "COMPLETE"  # Workflow evaluated successfully
    FAILED = "FAILED"  # Workflow execution failure


class VerificationOutcome(str, Enum):
    """Outcome of a verification workflow."""

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    PENDING = "PENDING"
    ERROR = "ERROR"
    USAGE_LIMIT = "USAGE_LIMIT"
    API_LIMIT = "API_LIMIT"


class RequestHeader:
    """Header names the SDK sends on every API request.

    Single source of truth for the wire header names. These are set by the SDK,
    not the caller, so the values can change here (with fallback handling if
    needed) without breaking integrators. API headers are ``Dodgeball-*`` to
    match the live API and the other SDKs; the ``Composer`` rebrand is not yet
    reflected in that contract. ``Composer-SDK-Version`` and ``Composer-SDK-Source``
    identify this SDK and are not API headers. Plain ``str`` constants (not an
    Enum) so they can be used directly as header keys without value/repr ambiguity.
    """

    SECRET_KEY = "Dodgeball-Secret-Key"
    VERIFICATION_ID = "Dodgeball-Verification-Id"
    SOURCE_TOKEN = "Dodgeball-Source-Token"
    CUSTOMER_ID = "Dodgeball-Customer-Id"
    SESSION_ID = "Dodgeball-Session-Id"
    SDK_VERSION = "Composer-SDK-Version"
    SDK_SOURCE = "Composer-SDK-Source"


# Keep in sync with the version in pyproject.toml
SDK_VERSION = "1.0.0"

# API Configuration
DEFAULT_API_URL = "https://api.dodgeballhq.com/"
DEFAULT_REQUEST_TIMEOUT_MS = 30 * 1000  # 30 seconds

# Polling Configuration
BASE_CHECKPOINT_POLLING_WAIT_MS = 100
MAX_POLLING_WAIT_MS = 2000
BASE_CHECKPOINT_MAX_TIMEOUT_MS = 10 * 60 * 1000  # 10 minutes
MAX_FAILURE_COUNT = 3
