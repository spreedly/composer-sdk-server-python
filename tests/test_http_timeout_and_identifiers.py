"""HTTP request timeouts and caller identifier validation."""

import contextlib
import itertools
import socket
import threading
import time
from unittest.mock import patch

import pytest
import responses

from composer.composer import Composer
from composer.constants import DEFAULT_REQUEST_TIMEOUT_MS, VerificationOutcome, VerificationStatus
from composer.logger import ComposerLogLevel
from composer.types import CheckpointEvent, CheckpointResponseOptions, ComposerConfig, TrackEvent
from composer.utilities import (
    contains_control_character,
    make_request,
    validate_caller_identifier,
    validate_caller_identifiers,
)


@contextlib.contextmanager
def stalling_tcp_server():
    """Accept connections but never send an HTTP response."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    server_socket.listen(5)
    port = server_socket.getsockname()[1]
    stop_event = threading.Event()

    def serve() -> None:
        server_socket.settimeout(0.5)
        while not stop_event.is_set():
            try:
                conn, _ = server_socket.accept()
                while not stop_event.is_set():
                    time.sleep(0.05)
                conn.close()
            except OSError:
                break
            except socket.timeout:
                continue

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        stop_event.set()
        server_socket.close()


@patch("composer.utilities.requests.post")
def test_make_request_default_timeout_uses_connect_read_tuple(mock_post):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"success": True}

    make_request(
        url="https://api.example.com/test",
        method="POST",
        headers={},
        body={},
    )

    assert mock_post.call_args.kwargs["timeout"] == (30.0, 30.0)


@patch("composer.utilities.requests.get")
def test_make_request_honors_request_timeout_ms_override(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"success": True}

    make_request(
        url="https://api.example.com/test",
        method="GET",
        headers={},
        request_timeout_ms=5000,
    )

    assert mock_get.call_args.kwargs["timeout"] == (5.0, 5.0)


def test_request_timeout_ms_override_bounds_stalling_upstream_quickly():
    with stalling_tcp_server() as port:
        config = ComposerConfig(
            api_url=f"http://127.0.0.1:{port}/",
            request_timeout_ms=500,
            log_level=ComposerLogLevel.NONE,
        )
        composer = Composer("test_secret", config)
        event = CheckpointEvent(ip="192.168.1.1")

        start = time.time()
        response = composer.checkpoint("test", event, session_id="sess123")
        elapsed = time.time() - start

    assert elapsed < 2.0
    assert response.success is False


def test_default_timeout_bounds_stalling_upstream_when_caller_passes_none():
    # Patched down from the real 30s default so the test does not wait that long.
    with stalling_tcp_server() as port, patch("composer.utilities.DEFAULT_REQUEST_TIMEOUT_MS", 500):
        start = time.time()

        data = make_request(
            url=f"http://127.0.0.1:{port}/checkpoint",
            method="POST",
            headers={},
            body={},
        )

        elapsed = time.time() - start

    assert elapsed < 2.0
    assert data == {"success": False, "errors": [{"code": 500, "message": "Internal Server Error"}]}


@responses.activate
def test_checkpoint_polling_budget_independent_from_request_timeout():
    """Long polling budget must not change per-request HTTP timeout wiring."""
    captured_timeouts = []

    def capture_make_request(*args, **kwargs):
        captured_timeouts.append(kwargs.get("request_timeout_ms"))
        url = kwargs["url"]
        if url.endswith("checkpoint"):
            return {
                "success": True,
                "version": "v1",
                "errors": [],
                "verification": {
                    "id": "ver123",
                    "status": VerificationStatus.PENDING.value,
                    "outcome": VerificationOutcome.PENDING.value,
                },
            }
        return {
            "success": True,
            "version": "v1",
            "errors": [],
            "verification": {
                "id": "ver123",
                "status": VerificationStatus.COMPLETE.value,
                "outcome": VerificationOutcome.APPROVED.value,
            },
        }

    config = ComposerConfig(log_level=ComposerLogLevel.NONE)
    composer = Composer("test_secret", config)
    event = CheckpointEvent(ip="192.168.1.1")
    options = CheckpointResponseOptions(timeout=120_000)

    with patch("composer.composer.make_request", side_effect=capture_make_request):
        response = composer.checkpoint(
            "test",
            event,
            session_id="sess123",
            options=options,
        )

    assert response.success is True
    assert len(captured_timeouts) == 2
    assert captured_timeouts == [DEFAULT_REQUEST_TIMEOUT_MS, DEFAULT_REQUEST_TIMEOUT_MS]


@pytest.mark.parametrize("invalid_value", [0, -1, 1.5, "abc", True])
def test_invalid_request_timeout_ms_logs_and_falls_back_to_default(invalid_value, capsys):
    config = ComposerConfig(log_level=ComposerLogLevel.ERROR, request_timeout_ms=invalid_value)
    composer = Composer("test_secret", config)

    assert composer.config.request_timeout_ms == DEFAULT_REQUEST_TIMEOUT_MS
    assert config.request_timeout_ms == invalid_value  # the caller's object is left alone
    assert "config.request_timeout_ms must be a positive integer" in capsys.readouterr().out


def test_valid_request_timeout_ms_is_kept_without_logging(capsys):
    composer = Composer(
        "test_secret", ComposerConfig(log_level=ComposerLogLevel.ERROR, request_timeout_ms=5000)
    )

    assert composer.config.request_timeout_ms == 5000
    assert capsys.readouterr().out == ""


def test_checkpoint_polls_at_least_once_when_budget_is_already_spent():
    pending = {
        "success": True,
        "version": "v1",
        "errors": [],
        "verification": {
            "id": "ver123",
            "status": VerificationStatus.PENDING.value,
            "outcome": VerificationOutcome.PENDING.value,
        },
    }
    composer = Composer("test_secret", ComposerConfig(log_level=ComposerLogLevel.NONE))

    # The clock jumps past the 1 ms budget before the loop is checked
    with (
        patch("composer.composer.make_request", return_value=pending) as mock_request,
        patch(
            "composer.composer.time.time",
            side_effect=itertools.chain([0.0], itertools.repeat(10.0)),
        ),
    ):
        response = composer.checkpoint(
            "test",
            CheckpointEvent(ip="192.168.1.1"),
            session_id="sess123",
            options=CheckpointResponseOptions(timeout=1),
        )

    assert mock_request.call_count == 2  # initial request + one poll
    assert response.success is True
    assert response.is_timeout() is False


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("session_id", "sess\x00id"),
        ("source_token", "token\x01"),
        ("user_id", "user\x7f"),
        ("use_verification_id", "ver\u0080"),
    ],
)
def test_validate_caller_identifier_rejects_control_characters(field_name, invalid_value):
    with pytest.raises(ValueError, match="must not contain control characters"):
        validate_caller_identifier(invalid_value, field_name)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("session_id", "sess\x00id"),
        ("source_token", "token\x01"),
        ("user_id", "user\x7f"),
        ("use_verification_id", "ver\u0080"),
    ],
)
@patch("composer.composer.make_request")
def test_checkpoint_rejects_control_characters_before_request(
    mock_make_request, field_name, invalid_value
):
    composer = Composer("test_secret")
    event = CheckpointEvent(ip="192.168.1.1")
    kwargs = {
        "checkpoint_name": "test",
        "event": event,
        "session_id": "sess123",
        "source_token": "",
        "user_id": "",
        "use_verification_id": "",
    }
    kwargs[field_name] = invalid_value

    with pytest.raises(ValueError, match="must not contain control characters"):
        composer.checkpoint(**kwargs)

    mock_make_request.assert_not_called()


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("session_id", "sess\x00id"),
        ("source_token", "token\x01"),
        ("user_id", "user\x7f"),
    ],
)
@patch("composer.composer.make_request")
def test_event_skips_control_characters_without_raising(
    mock_make_request, field_name, invalid_value, capsys
):
    composer = Composer("test_secret")
    event = TrackEvent(type="login")
    kwargs = {
        "event": event,
        "session_id": "sess123",
        "source_token": "",
        "user_id": "",
    }
    kwargs[field_name] = invalid_value

    composer.event(**kwargs)

    mock_make_request.assert_not_called()
    output = capsys.readouterr().out
    assert f"Composer event was not sent: Invalid {field_name}" in output
    assert invalid_value not in output


def test_contains_control_character_uses_unicode_cc_category():
    assert contains_control_character("\x00")
    assert contains_control_character("\u0080")
    assert not contains_control_character("valid-id")


def test_validate_caller_identifiers_allows_empty_values():
    validate_caller_identifiers()
