"""Main Composer client for interacting with the Composer API."""

import time
from dataclasses import replace
from typing import Any, Dict, Optional

from composer.constants import (
    BASE_CHECKPOINT_MAX_TIMEOUT_MS,
    BASE_CHECKPOINT_POLLING_WAIT_MS,
    DEFAULT_REQUEST_TIMEOUT_MS,
    MAX_FAILURE_COUNT,
    MAX_POLLING_WAIT_MS,
    ApiVersion,
    VerificationOutcome,
    VerificationStatus,
)
from composer.exceptions import (
    ComposerInvalidConfigError,
    ComposerMissingConfigError,
    ComposerMissingParameterError,
)
from composer.logger import ComposerLogLevel, Logger
from composer.types import (
    ApiError,
    CheckpointEvent,
    CheckpointResponse,
    CheckpointResponseOptions,
    ComposerConfig,
    TrackEvent,
    Verification,
)
from composer.utilities import (
    RequestFailedBody,
    construct_api_headers,
    construct_api_url,
    is_null_or_empty,
    make_request,
    redact_sensitive_fields,
    sleep,
    validate_caller_identifiers,
)


class Composer:
    """Main client for the Composer SDK."""

    def __init__(self, secret_key: str, config: Optional[ComposerConfig] = None):
        """
        Initialize the Composer client.

        Args:
            secret_key: Your Composer API secret key
            config: Optional configuration object

        Raises:
            ComposerMissingConfigError: If secret key is missing
            ComposerInvalidConfigError: If configuration is invalid
        """
        # Validate secret key
        if not secret_key:
            raise ComposerMissingConfigError("secretApiKey", secret_key)

        self.secret_key = secret_key

        # Merge with default config
        if config is None:
            config = ComposerConfig()
        self.config = config

        # Validate API version
        valid_versions = [v.value for v in ApiVersion]
        if self.config.api_version not in valid_versions:
            raise ComposerInvalidConfigError(
                "config.api_version", self.config.api_version, valid_versions
            )

        # Validate log level
        valid_log_levels = [
            ComposerLogLevel.TRACE,
            ComposerLogLevel.INFO,
            ComposerLogLevel.ERROR,
            ComposerLogLevel.NONE,
        ]
        if self.config.log_level not in valid_log_levels:
            raise ComposerInvalidConfigError(
                "config.log_level", self.config.log_level, valid_log_levels
            )

        # Set logger filter level
        Logger.filter_level = Logger.log_level_to_severity(self.config.log_level)

        # Resolved after the logger is configured so the message below respects log_level.
        # Anything other than a positive integer would fail every request the SDK makes.
        request_timeout_ms = self.config.request_timeout_ms
        is_usable = (
            isinstance(request_timeout_ms, int)
            and not isinstance(request_timeout_ms, bool)
            and request_timeout_ms > 0
        )
        if not is_usable:
            if request_timeout_ms is not None:
                Logger.error(
                    f"config.request_timeout_ms must be a positive integer. Ignoring "
                    f"{request_timeout_ms!r} and using the {DEFAULT_REQUEST_TIMEOUT_MS}ms default."
                ).log()
            # Copy rather than mutate, since the caller owns the config object
            self.config = replace(self.config, request_timeout_ms=DEFAULT_REQUEST_TIMEOUT_MS)

    def _create_error_response(self, code: int, message: str) -> CheckpointResponse:
        """Create a standard error response."""
        return CheckpointResponse(
            success=False,
            errors=[ApiError(code=code, message=message)],
            version=ApiVersion.V1.value,
            verification=Verification(
                id="",
                status=VerificationStatus.FAILED.value,
                outcome=VerificationOutcome.ERROR.value,
            ),
        )

    def event(
        self,
        event: TrackEvent,
        user_id: str = "",
        session_id: str = "",
        source_token: str = "",
    ) -> None:
        """
        Send a tracking event to the Composer API.

        Args:
            event: The event data to track
            user_id: Optional user identifier
            session_id: Session identifier. One of session_id or source_token is required.
            source_token: Source token. One of session_id or source_token is required.
        """
        if not event:
            self._skip_event("no event was provided")
            return

        if is_null_or_empty(event.type):
            self._skip_event("event.type is missing")
            return

        if is_null_or_empty(session_id) and is_null_or_empty(source_token):
            self._skip_event("Must provide either a sessionId or sourceToken")
            return

        try:
            validate_caller_identifiers(
                session_id=session_id,
                source_token=source_token,
                user_id=user_id,
            )
        except ValueError as e:
            # The message names the field, never its value.
            self._skip_event(str(e))
            return

        # Only an explicit False disables the SDK. None must not overwrite the default.
        if self.config.is_enabled is False:
            return

        # Ensure event has a timestamp
        if not event.event_time:
            event.event_time = int(time.time() * 1000)

        # Send event to API
        data = make_request(
            url=f"{construct_api_url(self.config.api_url, self.config.api_version)}track",
            method="POST",
            headers=construct_api_headers(self.secret_key, "", source_token, user_id, session_id),
            body={"type": event.type, "data": event.data, "eventTime": event.event_time},
            request_timeout_ms=self.config.request_timeout_ms,
        )
        # make_request returns only the body, so the HTTP status isn't available here.
        # It already logged a request that never got a response.
        request_failed = isinstance(data, RequestFailedBody)
        accepted = isinstance(data, dict) and data.get("success") is True
        if not request_failed and not accepted:
            Logger.error("Composer event was not accepted by the API.").log()

    def _skip_event(self, reason: str) -> None:
        Logger.error(f"Composer event was not sent: {reason}").log()

    def notify(
        self,
        event: TrackEvent,
        user_id: str = "",
        session_id: str = "",
        source_token: str = "",
    ) -> None:
        """Alias for event() for backward compatibility."""
        self.event(event, user_id, session_id, source_token)

    def track(
        self,
        event: TrackEvent,
        user_id: str = "",
        session_id: str = "",
        source_token: str = "",
    ) -> None:
        """Alias for event() for backward compatibility."""
        self.event(event, user_id, session_id, source_token)

    def checkpoint(
        self,
        checkpoint_name: str,
        event: CheckpointEvent,
        user_id: str = "",
        session_id: str = "",
        source_token: str = "",
        use_verification_id: str = "",
        options: Optional[CheckpointResponseOptions] = None,
    ) -> CheckpointResponse:
        """
        Submit a checkpoint to Composer and poll for verification if needed.

        Args:
            checkpoint_name: Name of the checkpoint to submit
            event: Event data for the checkpoint
            user_id: Optional user identifier
            session_id: Optional session identifier
            source_token: Optional source token
            use_verification_id: Optional verification ID to reuse
            options: Optional checkpoint response options

        Returns:
            CheckpointResponse with the verification result

        Raises:
            ComposerMissingParameterError: If required parameters are missing
        """
        # Validate required parameters
        if is_null_or_empty(checkpoint_name):
            raise ComposerMissingParameterError("checkpointName")

        if not event:
            raise ComposerMissingParameterError("event")

        if is_null_or_empty(session_id) and is_null_or_empty(source_token):
            raise ComposerMissingParameterError("Must provide either a sessionId or sourceToken")

        # Only an explicit False disables the SDK. None must not overwrite the default.
        if self.config.is_enabled is False:
            return CheckpointResponse(
                success=True,
                errors=[],
                version=ApiVersion.V1.value,
                verification=Verification(
                    id="COMPOSER_IS_DISABLED",
                    status=VerificationStatus.COMPLETE.value,
                    outcome=VerificationOutcome.APPROVED.value,
                ),
            )

        validate_caller_identifiers(
            session_id=session_id,
            source_token=source_token,
            user_id=user_id,
            use_verification_id=use_verification_id,
        )

        # Set up options
        if options is None:
            options = CheckpointResponseOptions()

        checkpoint_timeout = (
            options.timeout
            if options.timeout and options.timeout > 0
            else BASE_CHECKPOINT_MAX_TIMEOUT_MS
        )
        current_polling_wait = BASE_CHECKPOINT_POLLING_WAIT_MS

        # Prepare request options
        request_options: Dict[str, Any] = {
            "sync": options.sync,
        }

        num_failures = 0
        has_never_polled = True
        checkpoint_start_time = time.time() * 1000  # Convert to ms
        api_url = construct_api_url(self.config.api_url, self.config.api_version)
        event_body = {"type": checkpoint_name, "data": event.data}
        if event.ip:
            event_body["ip"] = event.ip

        # Submit checkpoint
        try:
            response_data = make_request(
                url=f"{api_url}checkpoint",
                method="POST",
                headers=construct_api_headers(
                    self.secret_key, use_verification_id, source_token, user_id, session_id
                ),
                body={
                    "event": event_body,
                    "options": request_options,
                },
                request_timeout_ms=self.config.request_timeout_ms,
            )
        except Exception as e:
            Logger.error("Failed to submit checkpoint", e).log()
            return self._create_error_response(500, "Internal Server Error")

        # Parse response
        response = self._parse_checkpoint_response(response_data)
        if not response:
            return self._create_error_response(500, "Unknown evaluation error")

        if not response.success:
            return response

        # Check if resolved
        is_resolved = response.verification.status != VerificationStatus.PENDING.value

        # Poll for completion if needed
        verification_id = response.verification.id

        while not is_resolved and (
            (time.time() * 1000 - checkpoint_start_time) < checkpoint_timeout or has_never_polled
        ):
            # Wait before polling
            sleep(current_polling_wait)

            # Exponential backoff
            current_polling_wait = min(current_polling_wait * 2, MAX_POLLING_WAIT_MS)
            has_never_polled = False

            # Poll verification endpoint
            try:
                response_data = make_request(
                    url=f"{api_url}verification/{verification_id}",
                    method="GET",
                    headers=construct_api_headers(
                        self.secret_key, use_verification_id, source_token, user_id, session_id
                    ),
                    request_timeout_ms=self.config.request_timeout_ms,
                )
                response = self._parse_checkpoint_response(response_data)

                if response and response.success:
                    status = response.verification.status
                    if not status:
                        num_failures += 1
                    else:
                        is_resolved = status != VerificationStatus.PENDING.value
                        num_failures = 0
                else:
                    num_failures += 1
            except Exception:
                num_failures += 1

            # Check for max failures
            if num_failures >= MAX_FAILURE_COUNT:
                Logger.error("Service Unavailable: Maximum retry count exceeded").log()
                return CheckpointResponse(
                    success=False,
                    errors=[
                        ApiError(
                            code=503, message="Service Unavailable: Maximum retry count exceeded"
                        )
                    ],
                    version=ApiVersion.V1.value,
                    verification=Verification(
                        id=verification_id,
                        status=VerificationStatus.FAILED.value,
                        outcome=VerificationOutcome.ERROR.value,
                    ),
                    is_timed_out=True,
                )

        if Logger.is_trace_enabled():
            Logger.trace(f"Returning response: {redact_sensitive_fields(response_data)}").log()
        if response is None:
            return self._create_error_response(500, "Unknown evaluation error")
        return response

    def _parse_checkpoint_response(self, data: Dict[str, Any]) -> Optional[CheckpointResponse]:
        """Parse API response data into a CheckpointResponse object."""
        try:
            verification_data = data.get("verification", {})
            verification = Verification(
                id=verification_data.get("id", ""),
                status=verification_data.get("status", ""),
                outcome=verification_data.get("outcome", ""),
                status_code=verification_data.get("statusCode"),
                next_steps=verification_data.get("nextSteps", []),
                step_data=verification_data.get("stepData"),
            )

            errors = [
                ApiError(code=e.get("code", 0), message=e.get("message", ""))
                for e in data.get("errors") or []
            ]

            return CheckpointResponse(
                success=data.get("success", False),
                errors=errors,
                version=data.get("version", ""),
                verification=verification,
                is_timed_out=data.get("isTimeout", False),
            )
        except Exception:
            return None

    # Helper methods
    @staticmethod
    def is_running(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint is still running with no verdict yet."""
        return checkpoint_response.is_running_check()

    @staticmethod
    def is_allowed(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint was approved."""
        return checkpoint_response.is_allowed()

    @staticmethod
    def is_denied(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint was denied."""
        return checkpoint_response.is_denied()

    @staticmethod
    def is_undecided(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint outcome is still pending."""
        return checkpoint_response.is_undecided()

    @staticmethod
    def has_error(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint encountered an error."""
        return checkpoint_response.has_error()

    @staticmethod
    def is_timeout(checkpoint_response: CheckpointResponse) -> bool:
        """Check if the checkpoint timed out."""
        return checkpoint_response.is_timeout()


# Backward compatibility alias
class Dodgeball(Composer):
    """Deprecated: Use Composer instead."""

    def __init__(self, secret_key: str, config: Optional[ComposerConfig] = None):
        import warnings

        warnings.warn(
            "Dodgeball is deprecated, use Composer instead", DeprecationWarning, stacklevel=2
        )
        super().__init__(secret_key, config)
