"""Tests for utilities module."""

import tomllib
from pathlib import Path

import composer
from composer.constants import SDK_VERSION, RequestHeader
from composer.utilities import (
    construct_api_headers,
    construct_api_url,
    is_null_or_empty,
    sleep,
)


def test_is_null_or_empty():
    """Test is_null_or_empty function."""
    assert is_null_or_empty(None) is True
    assert is_null_or_empty("") is True
    assert is_null_or_empty("test") is False
    assert is_null_or_empty("  ") is True


def test_construct_api_url():
    """Test API URL construction."""
    # With trailing slash
    url = construct_api_url("https://api.example.com/", "v1")
    assert url == "https://api.example.com/v1/"

    # Without trailing slash
    url = construct_api_url("https://api.example.com", "v1")
    assert url == "https://api.example.com/v1/"


def test_request_header_names():
    """Pin the wire header names sent to the API (single source of truth)."""
    assert RequestHeader.SECRET_KEY == "Dodgeball-Secret-Key"
    assert RequestHeader.VERIFICATION_ID == "Dodgeball-Verification-Id"
    assert RequestHeader.SOURCE_TOKEN == "Dodgeball-Source-Token"
    assert RequestHeader.CUSTOMER_ID == "Dodgeball-Customer-Id"
    assert RequestHeader.SESSION_ID == "Dodgeball-Session-Id"
    assert RequestHeader.SDK_VERSION == "Composer-SDK-Version"
    assert RequestHeader.SDK_SOURCE == "Composer-SDK-Source"


def test_construct_api_headers():
    """Test API header construction."""
    headers = construct_api_headers("secret123")
    assert headers["Content-Type"] == "application/json"
    assert headers[RequestHeader.SECRET_KEY] == "secret123"
    assert headers[RequestHeader.SDK_VERSION] == composer.__version__
    assert headers[RequestHeader.SDK_SOURCE] == "python-sdk"
    assert RequestHeader.VERIFICATION_ID not in headers


def test_sdk_version_matches_pyproject():
    """The header version and package metadata are updated together on release."""
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as pyproject_file:
        package_version = tomllib.load(pyproject_file)["project"]["version"]

    assert SDK_VERSION == package_version
    assert composer.__version__ == SDK_VERSION


def test_construct_api_headers_with_all_params():
    """Test API header construction with all optional parameters."""
    headers = construct_api_headers(
        secret_key="secret123",
        verification_id="ver123",
        source_token="src123",
        user_id="user123",
        session_id="sess123",
    )
    assert headers[RequestHeader.SECRET_KEY] == "secret123"
    assert headers[RequestHeader.VERIFICATION_ID] == "ver123"
    assert headers[RequestHeader.SOURCE_TOKEN] == "src123"
    assert headers[RequestHeader.CUSTOMER_ID] == "user123"
    assert headers[RequestHeader.SESSION_ID] == "sess123"


def test_sleep():
    """Test sleep function."""
    import time

    start = time.time()
    sleep(100)  # 100ms
    elapsed = time.time() - start
    assert elapsed >= 0.1  # Should sleep at least 100ms
    assert elapsed < 0.2  # But not too long
