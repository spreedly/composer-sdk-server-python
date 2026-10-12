"""Regression coverage for the safe logging default.

An integrator who passes no config must never see request bodies, response
bodies or event.ip in their logs.
"""

import responses

from composer.composer import Composer
from composer.constants import VerificationOutcome, VerificationStatus
from composer.logger import ComposerLogLevel, Logger, Severity
from composer.types import CheckpointEvent, ComposerConfig
from composer.utilities import redact_sensitive_fields

EVENT_IP = "203.0.113.7"
EVENT_EMAIL = "shopper@example.com"


def run_checkpoint(capsys, log_level=None):
    """Run a checkpoint against a stubbed API and return everything the SDK logged."""
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
                "stepData": {"email": EVENT_EMAIL},
            },
        },
        status=200,
    )

    config = ComposerConfig(log_level=log_level) if log_level else None
    composer = Composer("test_secret", config)
    composer.checkpoint(
        "purchase",
        CheckpointEvent(ip=EVENT_IP, data={"email": EVENT_EMAIL}),
        session_id="sess123",
    )

    return capsys.readouterr().out


def test_default_log_level_is_info():
    """A config the integrator never touched asks for INFO."""
    assert ComposerConfig().log_level == ComposerLogLevel.INFO


@responses.activate
def test_default_log_level_emits_nothing_for_a_checkpoint(capsys):
    output = run_checkpoint(capsys)

    assert Logger.filter_level == Severity.INFO
    assert output == ""


@responses.activate
def test_trace_log_level_logs_redacted_payloads(capsys):
    output = run_checkpoint(capsys, ComposerLogLevel.TRACE)

    assert VerificationStatus.COMPLETE.value in output
    assert "[REDACTED]" in output
    assert EVENT_IP not in output
    assert EVENT_EMAIL not in output


def test_redact_sensitive_fields_masks_end_user_fields():
    redacted = redact_sensitive_fields(
        {
            "event": {"type": "purchase", "ip": EVENT_IP, "data": {"email": EVENT_EMAIL}},
            "verification": {"id": "ver123", "stepData": {"email": EVENT_EMAIL}},
        }
    )

    assert redacted["event"]["type"] == "purchase"
    assert redacted["event"]["ip"] == "[REDACTED]"
    assert redacted["event"]["data"] == "[REDACTED]"
    assert redacted["verification"]["id"] == "ver123"
    assert redacted["verification"]["stepData"] == "[REDACTED]"


def test_redact_sensitive_fields_masks_next_steps():
    redacted = redact_sensitive_fields(
        {
            "verification": {
                "id": "ver123",
                "status": "BLOCKED",
                "nextSteps": [
                    {
                        "name": "STRIPE_IDENTITY",
                        "config": {"clientSecret": "vs_secret_value"},
                        "content": {"text": 'console.log("bundle");'},
                    }
                ],
            }
        }
    )

    assert redacted["verification"]["status"] == "BLOCKED"
    assert redacted["verification"]["nextSteps"] == "[REDACTED]"
    assert "vs_secret_value" not in str(redacted)


def test_is_trace_enabled_tracks_the_filter_level():
    original = Logger.filter_level
    try:
        Logger.filter_level = Severity.INFO
        assert Logger.is_trace_enabled() is False

        Logger.filter_level = Severity.TRACE
        assert Logger.is_trace_enabled() is True
    finally:
        Logger.filter_level = original
