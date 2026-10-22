# Spreedly Composer Server SDK for Python

## Table of Contents

- [Purpose](#purpose)
- [Prerequisites](#prerequisites)
- [Related](#related)
- [Installation](#installation)
- [Usage](#usage)
- [API](#api)
- [Development](#development)
- [License](#license)
- [Support](#support)

## Purpose

[Spreedly Composer](https://developer.spreedly.com) enables developers to decouple security logic from their application code. This has several benefits including:

- The ability to toggle and compare security services like fraud engines, MFA, KYC, and bot prevention.
- Faster responses to new attacks. When threats evolve and new vulnerabilities are identified, your application's security logic can be updated without changing a single line of code.
- The ability to put in placeholders for future security improvements while focusing on product development.
- A way to visualize all application security logic in one place.

The Composer Server SDK for Python makes integration with the Composer API easy and is maintained by the Spreedly team.

## Prerequisites

- Python 3.11 or higher
- You will need to obtain an API key for your application from the Composer developer center.

## Related

Check out the [Client SDK](https://npmjs.com/package/@dodgeball/trust-sdk-client) for how to integrate Composer into your frontend applications.

[Composer examples](https://github.com/spreedly/composer-examples) has a runnable example server for this SDK in `server/python`, and a web client that calls it.

## Installation

The package isn't on PyPI yet. Install it from GitHub:

```bash
pip install git+https://github.com/spreedly/composer-sdk-server-python.git
```

Or install from a local clone:

```bash
git clone https://github.com/spreedly/composer-sdk-server-python.git
cd composer-sdk-server-python
pip install -e .
```

## Usage

This example protects an order endpoint end to end. Your API calls a checkpoint before placing the order. When the workflow needs more input from the user, such as MFA, your frontend gathers it with the Client SDK and calls your API again with the verification ID. See [Identifiers](#identifiers) for what each ID is and [useVerification](#useverification) for how the second call works.

```python
# In your API
from composer import Composer, CheckpointEvent
from flask import Flask, request, jsonify, session
import ipaddress
import os

app = Flask(__name__)

# composer = Dodgeball(os.environ.get("DODGEBALL_SECRET_KEY"))  # The prior name is still supported.
composer = Composer(os.environ.get("SPREEDLY_SECRET_KEY"))

# Client IP for the risk engine. Callers must not choose this value.
# Default (TRUSTED_PROXY_COUNT=0): socket address, ignore X-Forwarded-For.
# Positive count: that many hops from the right of X-Forwarded-For; the hop must be an IP.
# Set TRUSTED_PROXY_COUNT only if your app runs behind trusted reverse proxies.
def get_ip(request):
    raw = os.environ.get("TRUSTED_PROXY_COUNT") or "0"
    try:
        hops = int(raw)
    except ValueError:
        hops = -1
    if hops < 0:
        raise ValueError("Cannot derive client IP: TRUSTED_PROXY_COUNT is not a valid hop count")

    header = request.headers.get("X-Forwarded-For") or ""
    parts = [part.strip() for part in header.split(",")]
    if hops == 0:
        candidate = request.remote_addr
    elif hops <= len(parts):
        candidate = parts[len(parts) - hops]
    else:
        candidate = None

    try:
        if candidate:
            ipaddress.ip_address(candidate)
            return candidate
    except ValueError:
        pass
    raise ValueError("Cannot derive client IP: no valid IP for this TRUSTED_PROXY_COUNT")

# The Client SDK expects the verification's fields in camelCase
def verification_json(verification):
    return {
        "id": verification.id,
        "status": verification.status,
        "outcome": verification.outcome,
        "nextSteps": verification.next_steps,
        "stepData": verification.step_data,
    }

@app.route("/api/orders", methods=["POST"])
def create_order():
    order_data = request.get_json()["order"]

    checkpoint_response = composer.checkpoint(
        checkpoint_name="PLACE_ORDER",
        event=CheckpointEvent(
            ip=get_ip(request),
            data={"order": order_data}
        ),
        source_token=request.headers.get("X-Dodgeball-Source-Token"),
        session_id=request.headers.get("X-Session-Id"),
        user_id=session.get("user_id"),
        use_verification_id=request.headers.get("X-Dodgeball-Verification-Id")
    )

    if composer.is_allowed(checkpoint_response):
        # placed_order = database.create_order(order_data)
        return jsonify({"order": order_data}), 200
    elif composer.is_denied(checkpoint_response):
        # Return the verification so the frontend can show the reason
        return jsonify({"verification": verification_json(checkpoint_response.verification)}), 403
    elif composer.is_running(checkpoint_response):
        # The workflow needs more input from the user (such as MFA or KYC)
        return jsonify({"verification": verification_json(checkpoint_response.verification)}), 202
    else:
        # No verdict: decide whether to return the error, proceed, retry, or reject. See Errors.
        return jsonify({"message": checkpoint_response.errors}), 500

if __name__ == "__main__":
    app.run(port=8080)
```

```js
// In your frontend, with the Client SDK
const placeOrder = async (order, previousVerificationId = null) => {
  const sourceToken = await dodgeball.getSourceToken();

  const endpointResponse = await axios.post("/api/orders", { order }, {
    headers: {
      "x-dodgeball-source-token": sourceToken,
      "x-dodgeball-verification-id": previousVerificationId
    },
    // Let the 202 and 403 responses through instead of throwing
    validateStatus: (status) => [200, 202, 403].includes(status)
  });

  if (endpointResponse.status === 200) {
    setIsOrderPlaced(true);
    return;
  }

  dodgeball.handleVerification(endpointResponse.data.verification, {
    onVerified: async (verification) => {
      // The user completed the extra step: call your API again with the verification ID
      await placeOrder(order, verification.id);
    },
    onApproved: async () => {
      setIsOrderPlaced(true);
    },
    onDenied: async (verification) => {
      setIsOrderDenied(true);
    },
    onError: async (error) => {
      setError(error);
      setIsPlacingOrder(false);
    }
  });
}
```

## API

### Configuration

---

The SDK requires a secret API key as the first argument to the constructor.

```python
from composer import Composer

composer = Composer("secret-api-key...")
```

Optionally, you can pass in several configuration options:

```python
from composer import Composer, ComposerConfig, ComposerLogLevel

composer = Composer(
    "secret-api-key...",
    ComposerConfig(
        api_version="v1",
        api_url="https://api.dodgeballhq.com",
        log_level=ComposerLogLevel.ERROR,
        is_enabled=True
    )
)
```

| Option | Default | Description |
| --- | --- | --- |
| `api_version` | `v1` | The Composer API version to use. |
| `api_url` | `https://api.dodgeballhq.com` | The base URL of the Spreedly Composer API. Useful for sending requests to different environments such as `https://api.sandbox.dodgeballhq.com`. |
| `log_level` | `INFO` | `TRACE`, `INFO`, `ERROR` or `NONE`. The SDK logs errors, plus redacted request and response payloads at `TRACE`, so `INFO` and `ERROR` currently log the same thing. See [Safe logging](#safe-logging). |
| `request_timeout_ms` | `30000` | How long each stage of an HTTP request (connecting, or waiting for data) may take, in milliseconds. Applies to every call the SDK makes. See [Timeouts](#timeouts). |
| `is_enabled` | `True` | When `False`, the SDK makes no API calls: `checkpoint` returns an approved response and `event` returns without sending anything. |

### Safe logging

---

At the default `INFO` level the SDK writes no request or response payloads: a successful checkpoint logs nothing, and `ERROR` reports request failures. Payload logging is opt-in through `TRACE`, and even there the fields that describe your end users or carry provider credentials (`ip`, `data`, `stepData` and `nextSteps`) are replaced with `[REDACTED]`, so a verbose log shows the shape of a request or response without carrying PII. Turn `TRACE` on only in environments where you are comfortable with that extra detail.

### Identifiers

---

`checkpoint` and `event` both take these. Provide a `session_id`, a `source_token`, or both. Identifiers must not contain control characters (such as newlines).

| Parameter | Required | Description |
| --- | --- | --- |
| `source_token` | Either this or `session_id` | A token representing the device making the request. Obtained from the [Client SDK](https://npmjs.com/package/@dodgeball/trust-sdk-client). |
| `session_id` | Either this or `source_token` | The current session ID of the request. |
| `user_id` | No | The ID of the user in your database, once you know it (for example, after registration). |
| `use_verification_id` | No | `checkpoint` only. The ID of a verification the user already completed. See [useVerification](#useverification). |

### Call a Checkpoint

---

Checkpoints represent key moments of risk in an application and are at the core of how Composer works. A checkpoint can represent any activity deemed to be a risk. Some common examples include: login, placing an order, redeeming a coupon, posting a review, changing bank account information, making a donation, transferring funds, creating a listing.

```python
from composer import CheckpointEvent

checkpoint_response = composer.checkpoint(
    checkpoint_name="CHECKPOINT_NAME",
    event=CheckpointEvent(
        ip="127.0.0.1",
        data={
            "transaction": {"amount": 100, "currency": "USD"},
            "paymentMethod": {"token": "ghi789"}
        }
    ),
    session_id="session_def456"
)
```

Along with the [identifiers](#identifiers), `checkpoint` takes:

| Parameter | Required | Description |
| --- | --- | --- |
| `checkpoint_name` | Yes | The name of the checkpoint to call. |
| `event` | Yes | A `CheckpointEvent` to send to the checkpoint. |
| `event.ip` | No | The IP address of the device where the request originated. Recommended whenever an end user is present; leave it out for checkpoints with no user, such as renewals. |
| `event.data` | No | Data your checkpoint's workflow uses. |
| `options` | No | A `CheckpointResponseOptions` with the fields below. |
| `options.sync` | No | Defaults to `False`. See [Timeouts](#timeouts). |
| `options.timeout` | No | How long the SDK keeps polling an unresolved verification, in milliseconds. Defaults to 10 minutes. See [Timeouts](#timeouts). |

### Timeouts

---

Two settings control timing and neither one caps the other. `request_timeout_ms` limits how long each stage of an HTTP request may take: connecting, or waiting for data. It applies to every call the SDK makes. It doesn't cap the request as a whole, so a response that keeps arriving slowly can take longer. `options.timeout` limits how long the SDK keeps polling for an unresolved verification, and defaults to 10 minutes. The SDK always polls at least once.

```python
from composer import CheckpointEvent, CheckpointResponseOptions, Composer, ComposerConfig

composer = Composer(
    "secret-api-key...",
    ComposerConfig(
        request_timeout_ms=5000  # Give up if connecting, or waiting for data, takes longer than 5 seconds
    )
)

checkpoint_response = composer.checkpoint(
    checkpoint_name="CHECKPOINT_NAME",
    event=CheckpointEvent(ip="127.0.0.1"),
    session_id="session_def456",
    options=CheckpointResponseOptions(
        timeout=10000  # Stop polling after 10 seconds and return whatever we have
    )
)
```

This example uses the default `sync=False`, which we recommend. The first request returns right away with a pending verification, and the SDK polls until it resolves, so each request is short and `request_timeout_ms` only guards against a hung connection. With `sync=True`, the first request waits on the server until the workflow finishes, so `request_timeout_ms` must be longer than your slowest workflow. Otherwise a slow but healthy checkpoint comes back as a failure.

When the polling budget runs out, the verification is simply still pending, which is not an error: `is_running` returns `True`, and you can resume later by passing the verification ID to `use_verification_id`. The exception is when the last poll before the budget ran out failed: you get that failure instead, with `success` `False`, and `has_error` returns `True`.

### Checkpoint Responses

---

Calling a checkpoint creates a verification in Composer. Its `status` and `outcome` determine how your application should proceed. Use the [utility methods](#utility-methods) rather than reading these fields directly.

```python
class CheckpointResponse:
    success: bool
    errors: List[ApiError]  # each has code and message
    version: str
    verification: Verification  # id, status, outcome, step_data, next_steps
    is_timed_out: bool
```

#### Response fields

| Property | Description |
| --- | --- |
| `success` | `False` when no verification result could be produced. See [Errors](#errors). A verification that failed while running still has `success=True`. |
| `errors` | `ApiError` objects with a `message` and a `code` (`0` when the API doesn't send one). Usually empty when `success` is `True`. |
| `version` | The version of the Composer API that was used to make the request. |
| `verification.id` | The ID of the verification that was created. |
| `verification.status` | `COMPLETE`, `PENDING`, `BLOCKED` or `FAILED`. |
| `verification.outcome` | `APPROVED`, `DENIED`, `PENDING`, `ERROR`, `USAGE_LIMIT` or `API_LIMIT`. |
| `verification.step_data` | Data from the workflow's steps. |
| `verification.next_steps` | Steps the Client SDK runs next, such as MFA. Send them to your frontend as `nextSteps`, as the [Usage](#usage) example does, so the Client SDK can start them right away. |
| `is_timed_out` | `True` when polling stopped after 3 failed polls in a row. See `is_timeout` below. |

#### Statuses and outcomes

| `status` | `outcome` | Utility method | Meaning |
| --- | --- | --- | --- |
| `COMPLETE` | `APPROVED` | `is_allowed` | Let the request proceed. |
| `COMPLETE` | `DENIED` | `is_denied` | Deny the request. Return the verification to the frontend to show the reason. |
| `BLOCKED` | `PENDING` | `is_running` | The workflow is waiting for input from the user, such as MFA or KYC. See [useVerification](#useverification). |
| `PENDING` | `PENDING` | `is_running` | Still processing when the polling budget ran out. Resume later with `use_verification_id`. |
| `COMPLETE` | `PENDING` | `is_undecided` | The workflow finished without reaching a verdict. Your application decides how to proceed. |
| `FAILED` | `ERROR` | `has_error` | The workflow failed while running, for example a third-party service was unavailable. |
| `FAILED` | `USAGE_LIMIT` | `has_error` | Your account reached its usage limit. |
| `FAILED` | `API_LIMIT` | `has_error` | Your account is sending too many requests right now, or is deactivated. |

### Utility Methods

---

Each method takes a checkpoint response and returns a boolean. The same checks are available as methods on the response itself (`checkpoint_response.is_allowed()` and so on), where `is_running` is named `is_running_check()`.

| Method | Returns `True` when |
| --- | --- |
| `composer.is_allowed(checkpoint_response)` | The request is allowed to proceed. |
| `composer.is_denied(checkpoint_response)` | The request is denied. |
| `composer.is_running(checkpoint_response)` | No verdict yet: the workflow is still processing or waiting on the user. |
| `composer.is_undecided(checkpoint_response)` | The workflow finished without a verdict. |
| `composer.has_error(checkpoint_response)` | `success` is `False`, or the workflow failed while running. |
| `composer.is_timeout(checkpoint_response)` | Polling stopped after 3 failed polls in a row. Running out of the polling `timeout` is not a timeout in this sense; see [Timeouts](#timeouts). |

### Errors

---

Only invalid input raises. Everything else comes back as a response, so a checkpoint never raises because of the network or the API.

| What happened | Raises? | What you get | Utility method |
| --- | --- | --- | --- |
| Missing secret key, or an invalid `api_version` or `log_level` | Yes, from the constructor: `ComposerMissingConfigError` or `ComposerInvalidConfigError` | | |
| Missing `checkpoint_name` or `event`, or neither `session_id` nor `source_token` | Yes, from `checkpoint`: `ComposerMissingParameterError` | | |
| An identifier contains a control character | Yes, from `checkpoint`: `ValueError` naming the field | | |
| The API rejected the request, for example there is no published workflow for the checkpoint name, or a usage or API limit was reached | No | `success=False`, the API's message in `errors` | `has_error` |
| Network error, request timeout, or a response the SDK can't read | No | `success=False`, a `500` in `errors` | `has_error` |
| 3 polls failed in a row | No | `success=False`, a `503` in `errors` | `has_error`, `is_timeout` |
| The workflow failed while running | No | `success=True`, status `FAILED`, outcome `ERROR` | `has_error` |
| Invalid input to `event` | Never | Nothing; the SDK logs it (see [Track an Event](#track-an-event)) | |

When `success` is `False` there is no verdict at all. Don't treat it as a denial; decide whether to retry, proceed, or reject.

### useVerification

---

Sometimes the workflow needs more input from the user before it can reach a verdict. For example, if the user must complete MFA, the checkpoint response has `status` `BLOCKED` and `outcome` `PENDING`, and `is_running` returns `True`. Return the verification to your frontend and pass it to the Client SDK's `handleVerification()` method, which gathers the input from the user. When the user is done, the frontend calls your API again with the verification ID, and your API passes it to `use_verification_id`. The checkpoint then uses that verification instead of creating a new one, so the user isn't asked twice. The [Usage](#usage) example shows the full flow.

**Important Note:** To prevent replay attacks, each verification ID can only be passed to `use_verification_id` once.

### Track an Event

---

You can track additional information about a user's journey by submitting tracking events from your server. This information will be added to the user's profile and is made available to checkpoints.

```python
from composer import TrackEvent

composer.event(
    event=TrackEvent(
        type="ADD_TO_CART",
        data={"product": {"id": "sku_123", "quantity": 1}}
    ),
    session_id="session_def456"
)
```

Along with the [identifiers](#identifiers), `event` takes:

| Parameter | Required | Description |
| --- | --- | --- |
| `event` | Yes | A `TrackEvent` to track. |
| `event.type` | Yes | A name for where the user is in their journey. Can be any non-blank string you choose. |
| `event.data` | No | Data to track. |
| `event.event_time` | No | When the event happened, in milliseconds since the epoch. Defaults to now. |

`event` doesn't raise for invalid input and returns nothing, so tracking can't break your request. Problems are logged at `ERROR` instead:

- If `event` is `None`, `event.type` is missing, neither `session_id` nor `source_token` is provided, or an identifier contains a control character, the event is not sent and the SDK logs `Composer event was not sent: <reason>`.
- If the API rejects the event, the SDK logs `Composer event was not accepted by the API.`
- If the request fails (network error or timeout), the SDK logs `There was an error making a request.`

`composer.notify()` and `composer.track()` are aliases for `event()`, kept for backward compatibility.

## Development

### Versioning

The SDK version is declared in two places that must be kept in sync when releasing:

- `pyproject.toml` (`version`)
- `composer/constants.py` (`SDK_VERSION`, sent in the `Composer-SDK-Version` header and exposed as `composer.__version__`)

Update both when bumping the version.

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/spreedly/composer-sdk-server-python.git
cd composer-sdk-server-python

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_composer.py

# Run with verbose output
pytest -v

# Generate HTML coverage report
pytest --cov-report=html
open htmlcov/index.html
```

### Code Quality

```bash
# Format code with Ruff
ruff format composer tests

# Lint with Ruff
ruff check composer tests

# Type checking with mypy
mypy composer
```

### Testing with the examples

To try local SDK changes end to end, clone [Composer examples](https://github.com/spreedly/composer-examples) next to this repository, point the `server/python` example at your checkout in its `requirements.txt`, and run it as the examples README describes:

```text
-e ../../../composer-sdk-server-python
```

The editable install picks up your changes when you restart the example.

## License

This SDK is released under the Apache-2.0 License. See [LICENSE](LICENSE) for details, and [THIRD-PARTY-LICENSES](THIRD-PARTY-LICENSES) for the licenses of its dependencies.

## Support

For support, please contact:

- Email: support@spreedly.com
- Documentation: https://developer.spreedly.com
