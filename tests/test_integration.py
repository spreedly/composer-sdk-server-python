"""Integration tests for the Composer client."""

import responses
from requests.exceptions import RequestException

from composer.composer import Composer
from composer.constants import RequestHeader, VerificationOutcome, VerificationStatus
from composer.logger import ComposerLogLevel
from composer.types import CheckpointEvent, CheckpointResponseOptions, ComposerConfig, TrackEvent


@responses.activate
def test_checkpoint_with_max_failures():
    """Test checkpoint with max consecutive failures."""
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

    # Mock 3 failed polling attempts
    for _ in range(3):
        responses.add(
            responses.GET,
            "https://api.dodgeballhq.com/v1/verification/ver123",
            body=RequestException("Connection error"),
        )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is False
    assert response.is_timed_out is True
    assert len(responses.calls) == 4  # 1 checkpoint + 3 polling attempts


@responses.activate
def test_checkpoint_non_json_responses_return_generic_errors():
    """A proxy error page (not JSON) never surfaces its parse error to the caller."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        body="<html>502 Bad Gateway</html>",
        status=502,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    response = composer.checkpoint("test", CheckpointEvent(ip="192.168.1.1"), session_id="sess123")

    assert [(e.code, e.message) for e in response.errors] == [(500, "Internal Server Error")]


@responses.activate
def test_checkpoint_non_json_polls_count_as_failures():
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
    for _ in range(3):
        responses.add(
            responses.GET,
            "https://api.dodgeballhq.com/v1/verification/ver123",
            body="<html>502 Bad Gateway</html>",
            status=502,
        )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    response = composer.checkpoint("test", CheckpointEvent(ip="192.168.1.1"), session_id="sess123")

    assert response.is_timed_out is True


@responses.activate
def test_checkpoint_request_exception():
    """Test checkpoint when API request fails."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        body=RequestException("API error"),
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is False
    assert [(e.code, e.message) for e in response.errors] == [(500, "Internal Server Error")]


@responses.activate
def test_checkpoint_returns_api_error_unchanged():
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={"success": False, "errors": [{"code": 401, "message": "Invalid secret key"}]},
        status=401,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    response = composer.checkpoint("test", CheckpointEvent(ip="192.168.1.1"), session_id="sess123")

    assert response.success is False
    assert [(e.code, e.message) for e in response.errors] == [(401, "Invalid secret key")]


@responses.activate
def test_event_does_not_raise_on_api_or_network_error():
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": False, "errors": [{"code": 401, "message": "Invalid secret key"}]},
        status=401,
    )
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        body=RequestException("connection refused"),
    )
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        body="<html>502 Bad Gateway</html>",
        status=502,
        content_type="text/html",
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    composer.event(TrackEvent(type="login"), session_id="sess123")
    composer.event(TrackEvent(type="login"), session_id="sess123")
    composer.event(TrackEvent(type="login"), session_id="sess123")

    assert len(responses.calls) == 3


@responses.activate
def test_event_logs_when_api_does_not_accept_it(capsys):
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": False, "errors": [{"message": "Invalid eventTime submitted."}]},
        status=400,
    )

    Composer("test_secret").event(TrackEvent(type="login"), session_id="sess123")

    assert "Composer event was not accepted by the API." in capsys.readouterr().out


@responses.activate
def test_event_network_failure_is_not_reported_as_an_api_rejection(capsys):
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        body=RequestException("connection refused"),
    )

    Composer("test_secret").event(TrackEvent(type="login"), session_id="sess123")

    output = capsys.readouterr().out
    assert output.count("There was an error making a request.") == 1
    assert "not accepted by the API" not in output


@responses.activate
def test_event_accepted_by_api_logs_nothing(capsys):
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True, "errors": []},
        status=201,
    )

    Composer("test_secret").event(TrackEvent(type="login"), session_id="sess123")

    assert capsys.readouterr().out == ""


@responses.activate
def test_checkpoint_invalid_response_data():
    """Test checkpoint with invalid response data."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={},  # Invalid/empty response
        status=200,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is False


@responses.activate
def test_checkpoint_with_source_token():
    """Test checkpoint using source_token instead of session_id."""
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
    response = composer.checkpoint("test", event, source_token="token123")

    assert response.success is True
    assert RequestHeader.SOURCE_TOKEN in responses.calls[0].request.headers


@responses.activate
def test_checkpoint_sync_mode():
    """Test checkpoint in synchronous mode."""
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
    options = CheckpointResponseOptions(sync=True)
    response = composer.checkpoint("test", event, session_id="sess123", options=options)

    assert response.success is True
    # Verify sync=true was sent in request body
    import json

    body = json.loads(responses.calls[0].request.body)
    assert body["options"]["sync"] is True


@responses.activate
def test_checkpoint_with_use_verification_id():
    """Test checkpoint with use_verification_id parameter."""
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
    response = composer.checkpoint(
        "test", event, session_id="sess123", use_verification_id="existing_ver"
    )

    assert response.success is True
    assert RequestHeader.VERIFICATION_ID in responses.calls[0].request.headers


@responses.activate
def test_event_with_auto_timestamp():
    """Test event automatically adds timestamp if not provided."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/track",
        json={"success": True},
        status=200,
    )

    composer = Composer("test_secret")
    event = TrackEvent(type="login", data={"method": "password"})
    # Don't set event_time
    composer.event(event, session_id="sess123")

    import json

    body = json.loads(responses.calls[0].request.body)
    assert "eventTime" in body
    assert body["eventTime"] > 0


@responses.activate
def test_checkpoint_with_custom_timeout():
    """Test checkpoint with custom timeout option."""
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
    options = CheckpointResponseOptions(timeout=5000)
    response = composer.checkpoint("test", event, session_id="sess123", options=options)

    assert response.success is True


@responses.activate
def test_checkpoint_unsuccessful_response():
    """Test checkpoint with unsuccessful API response."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": False,
            "version": "v1",
            "errors": [{"code": 400, "message": "Invalid request"}],
            "verification": {
                "id": "",
                "status": VerificationStatus.FAILED.value,
                "outcome": VerificationOutcome.ERROR.value,
            },
        },
        status=200,
    )

    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is False
    assert len(response.errors) > 0


@responses.activate
def test_checkpoint_with_user_id():
    """Test checkpoint with user_id parameter."""
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
    response = composer.checkpoint("test", event, session_id="sess123", user_id="user456")

    assert response.success is True
    assert RequestHeader.CUSTOMER_ID in responses.calls[0].request.headers
    assert responses.calls[0].request.headers[RequestHeader.CUSTOMER_ID] == "user456"


@responses.activate
def test_checkpoint_with_null_response():
    """Test checkpoint when _parse_checkpoint_response returns None."""
    responses.add(
        responses.POST,
        "https://api.dodgeballhq.com/v1/checkpoint",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": "this is a string not a dict",  # Invalid structure
        },
        status=200,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    response = composer.checkpoint("test", event, session_id="sess123")

    assert response.success is False
    assert "Unknown evaluation error" in response.errors[0].message


@responses.activate
def test_checkpoint_polling_times_out_with_unparseable_response():
    """If polling only yields unparseable responses then times out, return an error."""
    # Initial checkpoint is pending, so the client enters the polling loop.
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

    # Poll returns an unparseable verification (string, not dict) -> parse yields None.
    responses.add(
        responses.GET,
        "https://api.dodgeballhq.com/v1/verification/ver123",
        json={"success": True, "version": "v1", "errors": [], "verification": "not a dict"},
        status=200,
    )

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    # Tiny timeout: the loop enters, polls once, then exits on timeout before the
    # failure cap, leaving the last parsed response as None.
    options = CheckpointResponseOptions(timeout=50)
    response = composer.checkpoint("test", event, session_id="sess123", options=options)

    assert response.success is False
    assert "Unknown evaluation error" in response.errors[0].message


@responses.activate
def test_checkpoint_polling_with_missing_status():
    """Test checkpoint polling when status is missing in response."""
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

    # Mock polling response with missing status
    responses.add(
        responses.GET,
        "https://api.dodgeballhq.com/v1/verification/ver123",
        json={
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {"id": "ver123", "outcome": VerificationOutcome.PENDING.value},
        },
        status=200,
    )

    # Second poll with complete status
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


@responses.activate
def test_checkpoint_polling_with_unsuccessful_response():
    """Test checkpoint polling when response is unsuccessful."""
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

    # Mock unsuccessful polling response
    responses.add(
        responses.GET,
        "https://api.dodgeballhq.com/v1/verification/ver123",
        json={"success": False, "errors": [{"code": 500, "message": "Error"}]},
        status=200,
    )

    # Second poll successful
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


def test_static_helper_with_unsuccessful_response():
    """Test static helper methods with unsuccessful response."""
    from composer.types import CheckpointResponse, Verification

    response = CheckpointResponse(
        success=False,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1",
            status=VerificationStatus.PENDING.value,
            outcome=VerificationOutcome.PENDING.value,
        ),
    )

    assert Composer.is_running(response) is False


def test_all_static_helper_methods():
    """Test all static helper methods."""
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

    # Test is_denied
    response = CheckpointResponse(
        success=True,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1",
            status=VerificationStatus.COMPLETE.value,
            outcome=VerificationOutcome.DENIED.value,
        ),
    )
    assert Composer.is_denied(response) is True

    # Test is_undecided
    response = CheckpointResponse(
        success=True,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1",
            status=VerificationStatus.COMPLETE.value,
            outcome=VerificationOutcome.PENDING.value,
        ),
    )
    assert Composer.is_undecided(response) is True

    # Test has_error
    response = CheckpointResponse(
        success=False,
        errors=[],
        version="v1",
        verification=Verification(
            id="v1", status=VerificationStatus.FAILED.value, outcome=VerificationOutcome.ERROR.value
        ),
    )
    assert Composer.has_error(response) is True

    # Test is_timeout
    response = CheckpointResponse(
        success=False,
        errors=[],
        version="v1",
        verification=Verification(id="v1", status="PENDING", outcome="PENDING"),
        is_timed_out=True,
    )
    assert Composer.is_timeout(response) is True
