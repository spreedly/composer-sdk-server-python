"""Tests for Composer client."""

import json

import pytest
import responses

from composer.composer import Composer, Dodgeball
from composer.constants import VerificationOutcome, VerificationStatus
from composer.exceptions import (
    ComposerInvalidConfigError,
    ComposerMissingConfigError,
    ComposerMissingParameterError,
)
from composer.logger import ComposerLogLevel, Severity
from composer.types import (
    CheckpointEvent,
    ComposerConfig,
    TrackEvent,
)


def test_composer_init_missing_secret_key():
    """Test Composer initialization with missing secret key."""
    with pytest.raises(ComposerMissingConfigError) as exc_info:
        Composer("")
    assert "secretApiKey" in str(exc_info.value)


def test_composer_init_invalid_api_version():
    """Test Composer initialization with invalid API version."""
    config = ComposerConfig(api_version="v2")
    with pytest.raises(ComposerInvalidConfigError) as exc_info:
        Composer("test_secret", config)
    assert "api_version" in str(exc_info.value)


def test_composer_init_invalid_log_level():
    """Test Composer initialization with invalid log level."""
    config = ComposerConfig(log_level="DEBUG")
    with pytest.raises(ComposerInvalidConfigError) as exc_info:
        Composer("test_secret", config)
    assert "log_level" in str(exc_info.value)


def test_composer_init_success():
    """Test successful Composer initialization."""
    from composer.logger import Logger

    composer = Composer("test_secret")
    assert composer.secret_key == "test_secret"
    assert composer.config.api_version == "v1"
    assert Logger.filter_level == Severity.INFO


def test_composer_init_with_custom_config():
    """Test Composer initialization with custom config."""
    config = ComposerConfig(
        api_version="v1", api_url="https://custom.com/", log_level=ComposerLogLevel.ERROR
    )
    composer = Composer("test_secret", config)
    assert composer.config.api_url == "https://custom.com/"
    assert composer.config.log_level == ComposerLogLevel.ERROR


def test_checkpoint_missing_checkpoint_name():
    """Test checkpoint with missing checkpoint name."""
    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    with pytest.raises(ComposerMissingParameterError) as exc_info:
        composer.checkpoint("", event, session_id="sess123")
    assert "checkpointName" in str(exc_info.value)


def test_checkpoint_missing_event():
    """Test checkpoint with missing event."""
    composer = Composer("test_secret")
    with pytest.raises(ComposerMissingParameterError) as exc_info:
        composer.checkpoint("test_checkpoint", None, session_id="sess123")
    assert "event" in str(exc_info.value)


@pytest.mark.parametrize("event", [CheckpointEvent(), CheckpointEvent(ip="")])
@responses.activate
def test_checkpoint_omits_event_ip_when_not_given(event):
    """The API treats event.ip as optional, so it's left out of the request when empty."""
    responses.add(
        responses.POST,
        "https://api.example.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret", ComposerConfig(api_url="https://api.example.com/"))
    response = composer.checkpoint("test_checkpoint", event, session_id="sess123")

    assert response.verification.id == "ver123"
    assert json.loads(responses.calls[0].request.body)["event"] == {
        "type": "test_checkpoint",
        "data": {},
    }


def test_checkpoint_missing_session_and_source():
    """Test checkpoint with missing both session ID and source token."""
    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    with pytest.raises(ComposerMissingParameterError) as exc_info:
        composer.checkpoint("test_checkpoint", event)
    assert "sessionId or sourceToken" in str(exc_info.value)


def test_checkpoint_disabled_sdk():
    """Test checkpoint with disabled SDK returns approved."""
    config = ComposerConfig(is_enabled=False)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")

    response = composer.checkpoint("test_checkpoint", event, session_id="sess123")

    assert response.success is True
    assert response.verification.id == "COMPOSER_IS_DISABLED"
    assert response.verification.status == VerificationStatus.COMPLETE.value
    assert response.verification.outcome == VerificationOutcome.APPROVED.value


@responses.activate
def test_checkpoint_enabled_none_still_calls_api():
    """None keeps the default, so the checkpoint still calls the API."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret", ComposerConfig(is_enabled=None))
    response = composer.checkpoint(
        "test_checkpoint", CheckpointEvent(ip="192.168.1.1"), session_id="sess123"
    )

    assert response.verification.id == "ver123"
    assert len(responses.calls) == 1


@responses.activate
def test_checkpoint_complete_response():
    """Test checkpoint with immediate complete response (no polling)."""
    # Mock API response
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1", data={"amount": 100})
    response = composer.checkpoint("purchase", event, session_id="sess123")

    assert response.success is True
    assert response.verification.id == "ver123"
    assert response.verification.status == VerificationStatus.COMPLETE.value
    assert response.verification.outcome == VerificationOutcome.APPROVED.value
    assert len(responses.calls) == 1


@responses.activate
def test_checkpoint_parses_verification_step_fields():
    """status_code, next_steps, and step_data are parsed from the verification."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.BLOCKED.value,
                "outcome": VerificationOutcome.PENDING.value,
                "statusCode": 202,
                "nextSteps": [{"name": "MFA", "type": "challenge"}],
                "stepData": {"mfa": {"method": "sms"}},
            },
        },
        status=200,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("purchase", event, session_id="sess123")

    assert response.verification.status_code == 202
    assert response.verification.next_steps == [{"name": "MFA", "type": "challenge"}]
    assert response.verification.step_data == {"mfa": {"method": "sms"}}


@responses.activate
def test_checkpoint_step_fields_default_when_absent():
    """Missing step fields fall back to None/empty list rather than erroring."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("purchase", event, session_id="sess123")

    assert response.verification.status_code is None
    assert response.verification.next_steps == []
    assert response.verification.step_data is None


@responses.activate
def test_checkpoint_blocked_customer_with_null_errors_is_denied():
    """The API sends errors: null for a blocked customer; that is a denial, not a parse failure."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "",
            "errors": None,
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "statusCode": 403,
                "outcome": VerificationOutcome.DENIED.value,
                "stepData": {},
                "error": "",
                "nextSteps": [],
            },
        },
        status=201,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("purchase", event, session_id="sess123")

    assert response.success is True
    assert response.errors == []
    assert response.verification.id == "ver123"
    assert Composer.is_denied(response) is True
    assert Composer.has_error(response) is False


@responses.activate
def test_checkpoint_with_polling():
    """Test checkpoint with polling for completion."""
    # Mock initial checkpoint response (pending)
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.PENDING.value,
                "outcome": VerificationOutcome.PENDING.value,
            },
        },
        status=200,
    )

    # Mock verification polling response (complete)
    responses.add(
        responses.GET,
        "https://api.dodgeballhq.com/v1/verification/ver123",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        },
        status=200,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is True
    assert response.verification.status == VerificationStatus.COMPLETE.value
    assert len(responses.calls) == 2  # Initial + 1 poll


@responses.activate
def test_checkpoint_denied():
    """Test checkpoint with denied outcome."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.DENIED.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is True
    assert response.verification.outcome == VerificationOutcome.DENIED.value
    assert response.is_denied() is True


@responses.activate
def test_event():
    """Test sending a tracking event."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret")
    event = TrackEvent(type="login", data={"userId": "user123"})
    composer.event(event, session_id="sess123")

    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "https://api.dodgeballhq.com/v1/track"


def test_event_missing_event(capsys):
    """Test event with missing event data."""
    composer = Composer("test_secret")
    composer.event(None, session_id="sess123")
    assert "Composer event was not sent: no event was provided" in capsys.readouterr().out


@responses.activate
def test_event_missing_event_type(capsys):
    """Test event without a type is skipped before any request is sent."""
    composer = Composer("test_secret")
    composer.event(TrackEvent(type=None), session_id="sess123")
    assert "Composer event was not sent: event.type is missing" in capsys.readouterr().out
    assert len(responses.calls) == 0


def test_event_empty_event_type():
    """Test event with an empty type is skipped."""
    composer = Composer("test_secret")
    composer.event(TrackEvent(type=""), session_id="sess123")


def test_event_whitespace_event_type():
    """Test event with a whitespace-only type is skipped."""
    composer = Composer("test_secret")
    composer.event(TrackEvent(type="   "), session_id="sess123")


def test_event_missing_session_and_source(capsys):
    """Test event with neither session id nor source token."""
    composer = Composer("test_secret")
    composer.event(TrackEvent(type="login"))
    assert (
        "Composer event was not sent: Must provide either a sessionId or sourceToken"
        in capsys.readouterr().out
    )
    composer.event(TrackEvent(type="login"), session_id="   ", source_token="   ")


@responses.activate
def test_event_disabled_sdk():
    """Test event with disabled SDK doesn't call the API."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret", ComposerConfig(is_enabled=False))
    composer.event(TrackEvent(type="login", data={}), session_id="sess123")

    assert len(responses.calls) == 0


@responses.activate
def test_event_enabled_none_still_calls_api():
    """None keeps the default, so the event is still sent."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret", ComposerConfig(is_enabled=None))
    composer.event(TrackEvent(type="login", data={}), session_id="sess123")

    assert len(responses.calls) == 1


def test_event_disabled_sdk_missing_event():
    """Test a disabled SDK still skips a missing event without throwing."""
    composer = Composer("test_secret", ComposerConfig(is_enabled=False))
    composer.event(None, session_id="sess123")


def test_event_disabled_sdk_missing_event_type():
    """Test a disabled SDK still skips a missing event type without throwing."""
    composer = Composer("test_secret", ComposerConfig(is_enabled=False))
    composer.event(TrackEvent(type=""), session_id="sess123")


def test_event_disabled_sdk_accepts_either_identifier():
    """Test either identifier alone is enough, including while the SDK is disabled."""
    composer = Composer("test_secret", ComposerConfig(is_enabled=False))
    composer.event(TrackEvent(type="login"), session_id="sess123")
    composer.event(TrackEvent(type="login"), source_token="token123")


@responses.activate
def test_notify_alias():
    """Test notify is an alias for event."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret")
    event = TrackEvent(type="purchase")
    composer.notify(event, session_id="sess123")

    assert len(responses.calls) == 1


@responses.activate
def test_track_alias():
    """Test track is an alias for event."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret")
    event = TrackEvent(type="purchase")
    composer.track(event, session_id="sess123")

    assert len(responses.calls) == 1


def test_static_helpers():
    """Test static helper methods."""
    from composer.types import CheckpointResponse, Verification

    # Test is_allowed
    response = CheckpointResponse(
        success=True,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1",
            status=VerificationStatus.COMPLETE.value,
            outcome=VerificationOutcome.APPROVED.value,
        ),
    )
    assert Composer.is_allowed(response) is True
    assert Composer.is_denied(response) is False

    # Test is_running
    response = CheckpointResponse(
        success=True,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1",
            status=VerificationStatus.PENDING.value,
            outcome=VerificationOutcome.PENDING.value,
        ),
    )
    assert Composer.is_running(response) is True


def test_dodgeball_deprecated():
    """Test Dodgeball class shows deprecation warning."""
    with pytest.warns(DeprecationWarning, match="Dodgeball is deprecated"):
        dodgeball = Dodgeball("test_secret")
        assert isinstance(dodgeball, Composer)
