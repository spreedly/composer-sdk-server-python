"""Tests for types module."""

import pytest

from composer.constants import DEFAULT_REQUEST_TIMEOUT_MS, VerificationOutcome, VerificationStatus
from composer.logger import ComposerLogLevel
from composer.types import (
    ApiError,
    CheckpointEvent,
    CheckpointResponse,
    CheckpointResponseOptions,
    ComposerConfig,
    DodgeballConfig,
    TrackEvent,
    Verification,
)


def test_composer_config_defaults():
    """Test ComposerConfig default values."""
    config = ComposerConfig()
    assert config.api_version == "v1"
    assert config.api_url == "https://api.dodgeballhq.com/"
    assert config.log_level == ComposerLogLevel.INFO
    assert config.is_enabled is True
    assert config.request_timeout_ms == DEFAULT_REQUEST_TIMEOUT_MS


def test_composer_config_custom():
    """Test ComposerConfig with custom values."""
    config = ComposerConfig(
        api_version="v1",
        api_url="https://custom.api.com/",
        log_level=ComposerLogLevel.ERROR,
        is_enabled=False,
    )
    assert config.api_version == "v1"
    assert config.api_url == "https://custom.api.com/"
    assert config.log_level == ComposerLogLevel.ERROR
    assert config.is_enabled is False


def test_dodgeball_config_alias():
    """Test DodgeballConfig is an alias for ComposerConfig."""
    config = DodgeballConfig()
    assert isinstance(config, ComposerConfig)


def test_checkpoint_event():
    """Test CheckpointEvent creation."""
    event = CheckpointEvent(ip="192.168.1.1", data={"key": "value"})
    assert event.ip == "192.168.1.1"
    assert event.data["key"] == "value"


def test_checkpoint_event_defaults():
    """Test CheckpointEvent defaults."""
    event = CheckpointEvent()
    assert event.ip is None
    assert event.data == {}


def test_track_event():
    """Test TrackEvent creation."""
    event = TrackEvent(type="purchase", data={"amount": 100}, event_time=1234567890)
    assert event.type == "purchase"
    assert event.data["amount"] == 100
    assert event.event_time == 1234567890


def test_track_event_defaults():
    """Test TrackEvent with defaults."""
    event = TrackEvent(type="login")
    assert event.type == "login"
    assert event.data == {}
    assert event.event_time is None


def test_checkpoint_response_options():
    """Test CheckpointResponseOptions."""
    options = CheckpointResponseOptions(sync=True, timeout=5000)
    assert options.sync is True
    assert options.timeout == 5000


def test_checkpoint_response_options_defaults():
    """Test CheckpointResponseOptions defaults."""
    options = CheckpointResponseOptions()
    assert options.sync is False
    assert options.timeout is None


def test_api_error():
    """Test ApiError creation."""
    error = ApiError(code=400, message="Bad request")
    assert error.code == 400
    assert error.message == "Bad request"


def test_verification():
    """Test Verification creation."""
    verification = Verification(id="ver123", status="COMPLETE", outcome="APPROVED")
    assert verification.id == "ver123"
    assert verification.status == "COMPLETE"
    assert verification.outcome == "APPROVED"


def test_verification_step_field_defaults():
    """Test Verification step fields default to None/empty."""
    verification = Verification(id="ver123", status="COMPLETE", outcome="APPROVED")
    assert verification.status_code is None
    assert verification.next_steps == []
    assert verification.step_data is None


def test_verification_with_step_fields():
    """Test Verification accepts status_code, next_steps, and step_data."""
    verification = Verification(
        id="ver123",
        status="BLOCKED",
        outcome="PENDING",
        status_code=202,
        next_steps=[{"name": "MFA"}],
        step_data={"mfa": {"method": "sms"}},
    )
    assert verification.status_code == 202
    assert verification.next_steps == [{"name": "MFA"}]
    assert verification.step_data == {"mfa": {"method": "sms"}}


def test_checkpoint_response():
    """Test CheckpointResponse creation."""
    verification = Verification(id="ver123", status="COMPLETE", outcome="APPROVED")
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.success is True
    assert response.errors == []
    assert response.version == "v1"
    assert response.verification.id == "ver123"
    assert response.is_timed_out is False


def test_checkpoint_response_is_allowed():
    """Test CheckpointResponse.is_allowed for approved and complete."""
    verification = Verification(
        id="ver123",
        status=VerificationStatus.COMPLETE.value,
        outcome=VerificationOutcome.APPROVED.value,
    )
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.is_allowed() is True


def test_checkpoint_response_is_denied():
    """Test CheckpointResponse.is_denied for denied and complete."""
    verification = Verification(
        id="ver123",
        status=VerificationStatus.COMPLETE.value,
        outcome=VerificationOutcome.DENIED.value,
    )
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.is_denied() is True


def test_checkpoint_response_is_running():
    """Test CheckpointResponse.is_running_check for pending status."""
    verification = Verification(
        id="ver123",
        status=VerificationStatus.PENDING.value,
        outcome=VerificationOutcome.PENDING.value,
    )
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.is_running_check() is True


def test_checkpoint_response_is_undecided():
    """Test CheckpointResponse.is_undecided for pending outcome."""
    verification = Verification(
        id="ver123",
        status=VerificationStatus.COMPLETE.value,
        outcome=VerificationOutcome.PENDING.value,
    )
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.is_undecided() is True


def test_checkpoint_response_has_error():
    """Test CheckpointResponse.has_error for unsuccessful response."""
    verification = Verification(
        id="ver123", status=VerificationStatus.FAILED.value, outcome=VerificationOutcome.ERROR.value
    )
    response = CheckpointResponse(success=False, errors=[], version="v1", verification=verification)
    assert response.has_error() is True


def test_checkpoint_response_has_error_with_error_outcome():
    """Test CheckpointResponse.has_error for error outcome."""
    verification = Verification(
        id="ver123",
        status=VerificationStatus.COMPLETE.value,
        outcome=VerificationOutcome.ERROR.value,
    )
    response = CheckpointResponse(success=True, errors=[], version="v1", verification=verification)
    assert response.has_error() is True


@pytest.mark.parametrize(
    ("success", "status", "outcome", "expected"),
    [
        # expected: (is_allowed, is_denied, is_running_check, is_undecided, has_error)
        (True, "PENDING", "DENIED", (False, True, False, False, False)),
        (True, "BLOCKED", "DENIED", (False, True, False, False, False)),
        (True, "BLOCKED", "APPROVED", (False, False, False, False, False)),
        (True, "PENDING", "PENDING", (False, False, True, False, False)),
        (True, "FAILED", "ERROR", (False, False, False, False, True)),
        (False, "COMPLETE", "APPROVED", (False, False, False, False, True)),
        (False, "COMPLETE", "DENIED", (False, False, False, False, True)),
        (False, "PENDING", "PENDING", (False, False, False, False, True)),
    ],
)
def test_checkpoint_response_helpers_require_success(success, status, outcome, expected):
    verification = Verification(id="ver123", status=status, outcome=outcome)
    response = CheckpointResponse(
        success=success, errors=[], version="v1", verification=verification
    )
    assert (
        response.is_allowed(),
        response.is_denied(),
        response.is_running_check(),
        response.is_undecided(),
        response.has_error(),
    ) == expected


def test_checkpoint_response_is_timeout():
    """Test CheckpointResponse.is_timeout."""
    verification = Verification(id="ver123", status="PENDING", outcome="PENDING")
    response = CheckpointResponse(
        success=False, errors=[], version="v1", verification=verification, is_timed_out=True
    )
    assert response.is_timeout() is True
