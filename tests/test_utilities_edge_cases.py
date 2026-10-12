"""Tests for utilities with edge cases."""

from unittest.mock import patch

import pytest
from requests.exceptions import Timeout

from composer.logger import Logger, Severity
from composer.utilities import make_request, sleep_async


def test_make_request_unsupported_method():
    """Test make_request with unsupported HTTP method."""
    with pytest.raises(ValueError, match="Unsupported HTTP method"):
        make_request(
            url="https://api.example.com/test",
            method="DELETE",
            headers={},
        )


@patch("composer.utilities.requests.post")
def test_make_request_timeout(mock_post, capsys):
    """A timeout returns a generic error body instead of raising; only the log has the URL."""
    mock_post.side_effect = Timeout("Read timed out for https://api.example.com/test")
    Logger.filter_level = Severity.ERROR

    data = make_request(
        url="https://api.example.com/test",
        method="POST",
        headers={},
        body={},
        request_timeout_ms=1000,
    )

    output = capsys.readouterr().out
    assert data == {"success": False, "errors": [{"code": 500, "message": "Internal Server Error"}]}
    assert "Read timed out for https://api.example.com/test" in output


def test_make_request_keeps_an_unsendable_header_value_out_of_logs(capsys):
    # A key read from a file often ends in a newline; requests.InvalidHeader echoes it
    Logger.filter_level = Severity.ERROR
    data = make_request(
        url="https://api.example.com/test",
        method="POST",
        headers={"Dodgeball-Secret-Key": "sk_test_FAKE123\n"},
        body={},
    )

    output = capsys.readouterr().out
    assert data == {"success": False, "errors": [{"code": 500, "message": "Internal Server Error"}]}
    assert "sk_test_FAKE123" not in output
    assert "A request header has a character that can't be sent, such as a newline." in output


@patch("composer.utilities.requests.post")
def test_make_request_keeps_a_non_latin1_header_error_out_of_logs(mock_post, capsys):
    # http.client encodes headers as Latin-1 after connect; the exception's .object is the key.
    mock_post.side_effect = UnicodeEncodeError(
        "latin-1", "sk_test_FAKE123€", 15, 16, "ordinal not in range(256)"
    )
    Logger.filter_level = Severity.ERROR
    data = make_request(
        url="https://api.example.com/test",
        method="POST",
        headers={"Dodgeball-Secret-Key": "sk_test_FAKE123€"},
        body={},
    )

    output = capsys.readouterr().out
    assert data == {"success": False, "errors": [{"code": 500, "message": "Internal Server Error"}]}
    assert "sk_test_FAKE123" not in output
    assert "A request header has a character that can't be sent, such as a newline." in output


@pytest.mark.asyncio
async def test_sleep_async():
    """Test async sleep function."""
    import time

    start = time.time()
    await sleep_async(100)  # 100ms
    elapsed = time.time() - start
    assert elapsed >= 0.1  # Should sleep at least 100ms
    assert elapsed < 0.2  # But not too long
