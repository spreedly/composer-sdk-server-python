# Changelog

## 1.0.1 (2026-10-30)

No changes to the SDK's code.

### Changed
- The README's Client SDK links point to `@spreedly/composer-sdk-client`.
- The SBOM on the GitHub Release gives its root component the package's purl, `pkg:pypi/spreedly-composer-sdk-server@1.0.1`.

## 1.0.0 (2026-10-23)

First release as `spreedly-composer-sdk-server`. If you're upgrading from `dodgeball-server-sdk`, read **Changed** and **Removed**.

### Added
- `request_timeout_ms` config option: how long each stage of an HTTP request may take, default 30000 ms.
- `notify()` and `track()` as aliases of `event()`.
- `event()` logs an error when an event isn't sent or the API doesn't accept it.
- At `TRACE`, `ip`, `data`, `stepData` and `nextSteps` are redacted in logged payloads.

### Changed
- The package is now `spreedly-composer-sdk-server`, imported from `composer`, and the main class is `Composer`. `Dodgeball`, `DodgeballConfig`, `DodgeballApiVersion` and `DodgeballLogLevel` can still be imported from `composer` as aliases (`Dodgeball` emits a `DeprecationWarning`).
- Requires Python 3.11 or later. The only dependency is `requests` 2.32.4 or later.
- `checkpoint` and `event` are no longer `async`. Remove `await`.
- `post_event(...)` is now `event(event, user_id, session_id, source_token)` and returns `None`. Use keyword arguments, because the order changed.
- `checkpoint` is now `checkpoint(checkpoint_name, event, user_id, session_id, source_token, use_verification_id, options)`, and `event` is a `CheckpointEvent(ip, data)` with an optional `ip`. Use keyword arguments, because the order changed.
- `DodgeballConfig` is now `ComposerConfig(api_version, api_url, log_level, is_enabled, request_timeout_ms)`. Use keyword arguments, because the order changed.
- The constructor raises `ComposerMissingConfigError` for an empty secret key and `ComposerInvalidConfigError` for an unsupported `api_version` or `log_level`.
- `checkpoint` raises `ComposerMissingParameterError` for missing input (was `TypeError`), so update any `except TypeError`. A `source_token` can be used instead of `session_id`. An identifier containing a control character raises `ValueError`.
- `event()` doesn't raise for invalid input, such as `event=None`, a missing `event.type` or missing identifiers. It logs the problem and sends nothing.
- When disabled, `event()` sends nothing, and the placeholder verification ID is `COMPOSER_IS_DISABLED` (was `DODGEBALL_IS_DISABLED`).
- `sync=True` is now sent to the API, so the first request waits for the workflow to finish and is bound by `request_timeout_ms`. The default is still `False`.
- Polling backs off to a 2 second ceiling and stops after `options.timeout`, default 10 minutes. A still-pending verification is returned; check `is_running()` and resume with `use_verification_id`.
- `is_timeout()` is `True` only after 3 consecutive failed polls, which return `success=False` with a `503`.
- Each request is made once, with no retries. A network failure or unreadable response returns `success=False` with a `500` in `errors` instead of raising. Add your own retry if you need one.
- Response types are dataclasses with snake_case fields (`is_timed_out`, `next_steps`, `step_data`). Errors are `ApiError(code, message)`.
- `is_running` requires the outcome to be `PENDING` as well as the status to be `PENDING` or `BLOCKED`.
- `has_error` is `True` when `success` is `False` or the outcome is `ERROR`.
- Events no longer send `ip`, and `event_time` defaults to the current time.
- Logs are JSON lines on stdout, filtered by `log_level` (`TRACE`, `INFO`, `ERROR`, `NONE`; default `INFO`).

### Removed
- `webhook` from `CheckpointResponseOptions`. Passing it raises `TypeError`; remove it.
- The `logger` config argument. Use `log_level`.
- The `dodgeball.*` module paths and the pydantic types (`DodgeballEvent`, `DodgeballCheckpointResponse`, `DodgeballVerification`, `DodgeballError`, `DodgeballResponse`).
- `verification.error`.
- The `httpx`, `pydantic`, `aiohttp`, `python-dotenv` and `aiohttp-cors` dependencies.

### Fixed
- `is_undecided` returns `True` when the status is `COMPLETE` and the outcome is `PENDING`. It always returned `False`.
