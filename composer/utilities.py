"""Utility functions for the Composer SDK."""

import asyncio
import time
import unicodedata
from typing import Any, Dict, Optional, Tuple

import requests

from composer.constants import DEFAULT_REQUEST_TIMEOUT_MS, SDK_VERSION, RequestHeader
from composer.logger import Logger

# Fields that carry end-user information and are masked before anything is logged.
# nextSteps is included because a blocked checkpoint returns integration config
# (including provider client secrets) alongside the full client integration bundle.
SENSITIVE_FIELDS = ("ip", "data", "stepData", "nextSteps")
REDACTED = "[REDACTED]"


def redact_sensitive_fields(payload: Any) -> Any:
    """Return a copy of a payload with end-user fields masked.

    Verbose logs then show the shape of a request or response without exposing PII.
    """
    if isinstance(payload, list):
        return [redact_sensitive_fields(entry) for entry in payload]

    if not isinstance(payload, dict):
        return payload

    return {
        key: REDACTED if key in SENSITIVE_FIELDS else redact_sensitive_fields(value)
        for key, value in payload.items()
    }


def is_null_or_empty(value: Optional[str]) -> bool:
    """Check if a string is None, empty or only whitespace."""
    return value is None or value.strip() == ""


def contains_control_character(value: str) -> bool:
    """Return True if value contains a Unicode control character (category Cc)."""
    return any(unicodedata.category(char) == "Cc" for char in value)


def validate_caller_identifier(value: str, field_name: str) -> None:
    """Reject caller-supplied identifiers that contain Unicode control characters."""
    if value and contains_control_character(value):
        raise ValueError(f"Invalid {field_name}: must not contain control characters")


def validate_caller_identifiers(
    session_id: str = "",
    source_token: str = "",
    user_id: str = "",
    use_verification_id: str = "",
) -> None:
    """Validate all optional caller-supplied identifier fields."""
    validate_caller_identifier(session_id, "session_id")
    validate_caller_identifier(source_token, "source_token")
    validate_caller_identifier(user_id, "user_id")
    validate_caller_identifier(use_verification_id, "use_verification_id")


def construct_api_url(base_url: str, api_version: str) -> str:
    """Construct the full API URL from base URL and version."""
    # Ensure base URL ends with /
    if not base_url.endswith("/"):
        base_url += "/"
    return f"{base_url}{api_version}/"


def construct_api_headers(
    secret_key: str,
    verification_id: str = "",
    source_token: str = "",
    user_id: str = "",
    session_id: str = "",
) -> Dict[str, str]:
    """Construct the headers for an API request."""
    headers = {
        "Content-Type": "application/json",
        RequestHeader.SECRET_KEY: secret_key,
        RequestHeader.SDK_VERSION: SDK_VERSION,
        RequestHeader.SDK_SOURCE: "python-sdk",
    }

    if verification_id:
        headers[RequestHeader.VERIFICATION_ID] = verification_id
    if source_token:
        headers[RequestHeader.SOURCE_TOKEN] = source_token
    if user_id:
        headers[RequestHeader.CUSTOMER_ID] = user_id
    if session_id:
        headers[RequestHeader.SESSION_ID] = session_id

    return headers


def _request_timeout_tuple(request_timeout_ms: int) -> Tuple[float, float]:
    timeout_seconds = request_timeout_ms / 1000.0
    return (timeout_seconds, timeout_seconds)


class RequestFailedBody(Dict[str, Any]):
    """Stand-in body make_request returns when a request never got an HTTP response.

    A distinct type, rather than a key, so a real response body can't imitate it.
    """


def make_request(
    url: str,
    method: str,
    headers: Dict[str, str],
    body: Optional[Dict[str, Any]] = None,
    request_timeout_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Make an HTTP request to the API.

    Args:
        url: The full URL to request
        method: HTTP method (GET, POST, etc.)
        headers: Request headers
        body: Optional request body (will be JSON-encoded)
        request_timeout_ms: Per-request connect/read timeout in milliseconds

    Returns:
        The JSON response as a dict, whatever the HTTP status. A request that fails to
        complete (network error, timeout) or returns a body that isn't JSON gets a generic
        500 error body instead of raising.
    """
    effective_timeout_ms = (
        request_timeout_ms if request_timeout_ms is not None else DEFAULT_REQUEST_TIMEOUT_MS
    )
    request_timeout = _request_timeout_tuple(effective_timeout_ms)

    if body is not None and Logger.is_trace_enabled():
        Logger.trace(f"Request body: {redact_sensitive_fields(body)}").log()

    try:
        if method.upper() == "POST":
            response = requests.post(url, json=body, headers=headers, timeout=request_timeout)
        elif method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=request_timeout)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    except (requests.RequestException, UnicodeEncodeError) as e:
        # These messages can include the header value, which can be the secret key.
        if isinstance(e, (requests.exceptions.InvalidHeader, UnicodeEncodeError)):
            Logger.error(
                "A request header has a character that can't be sent, such as a newline."
            ).log()
        else:
            # Other request errors (timeouts, connection refused) keep their exception text.
            Logger.error("There was an error making a request.", e).log()
        return RequestFailedBody(
            success=False, errors=[{"code": 500, "message": "Internal Server Error"}]
        )

    # Non-2xx bodies carry the API's own error, so they're returned as-is.
    try:
        data: Dict[str, Any] = response.json()
    except ValueError as e:
        Logger.error("The Composer API returned a response that is not valid JSON.", e).log()
        return {"success": False, "errors": [{"code": 500, "message": "Internal Server Error"}]}
    return data


def sleep(milliseconds: int) -> None:
    """Sleep for the specified number of milliseconds."""
    time.sleep(milliseconds / 1000.0)


async def sleep_async(milliseconds: int) -> None:
    """Async sleep for the specified number of milliseconds."""
    await asyncio.sleep(milliseconds / 1000.0)
