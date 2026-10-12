"""Tests for constants module."""

from composer.constants import (
    BASE_CHECKPOINT_MAX_TIMEOUT_MS,
    BASE_CHECKPOINT_POLLING_WAIT_MS,
    DEFAULT_API_URL,
    DEFAULT_REQUEST_TIMEOUT_MS,
    MAX_FAILURE_COUNT,
    MAX_POLLING_WAIT_MS,
    ApiVersion,
    VerificationOutcome,
    VerificationStatus,
)


def test_api_version():
    """Test API version enum."""
    assert ApiVersion.V1.value == "v1"


def test_verification_status():
    """Test verification status enum values."""
    assert VerificationStatus.PENDING.value == "PENDING"
    assert VerificationStatus.BLOCKED.value == "BLOCKED"
    assert VerificationStatus.COMPLETE.value == "COMPLETE"
    assert VerificationStatus.FAILED.value == "FAILED"


def test_verification_outcome():
    """Test verification outcome enum values."""
    assert VerificationOutcome.APPROVED.value == "APPROVED"
    assert VerificationOutcome.DENIED.value == "DENIED"
    assert VerificationOutcome.PENDING.value == "PENDING"
    assert VerificationOutcome.ERROR.value == "ERROR"
    assert VerificationOutcome.USAGE_LIMIT.value == "USAGE_LIMIT"
    assert VerificationOutcome.API_LIMIT.value == "API_LIMIT"


def test_default_api_url():
    """Test default API URL."""
    assert DEFAULT_API_URL == "https://api.dodgeballhq.com/"


def test_default_request_timeout_ms():
    """Test default HTTP request timeout constant."""
    assert DEFAULT_REQUEST_TIMEOUT_MS == 30_000


def test_polling_constants():
    """Test polling configuration constants."""
    assert BASE_CHECKPOINT_POLLING_WAIT_MS == 100
    assert MAX_POLLING_WAIT_MS == 2000
    assert BASE_CHECKPOINT_MAX_TIMEOUT_MS == 10 * 60 * 1000
    assert MAX_FAILURE_COUNT == 3
