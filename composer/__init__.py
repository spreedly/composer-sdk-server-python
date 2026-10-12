"""
Composer Server SDK for Python

This SDK provides a Python interface to the Composer API for transaction monitoring
and verification.
"""

from composer.composer import Composer, Dodgeball
from composer.constants import SDK_VERSION
from composer.exceptions import (
    ComposerException,
    ComposerInvalidConfigError,
    ComposerMissingConfigError,
    ComposerMissingParameterError,
)
from composer.logger import ComposerLogLevel, DodgeballLogLevel
from composer.types import (
    ApiError,
    CheckpointEvent,
    CheckpointResponse,
    CheckpointResponseOptions,
    ComposerApiVersion,
    ComposerConfig,
    DodgeballApiVersion,
    DodgeballConfig,
    TrackEvent,
    Verification,
    VerificationOutcome,
    VerificationStatus,
)

__version__ = SDK_VERSION
__all__ = [
    "Composer",
    "Dodgeball",
    "ComposerLogLevel",
    "DodgeballLogLevel",
    "ComposerApiVersion",
    "DodgeballApiVersion",
    "ComposerConfig",
    "DodgeballConfig",
    "CheckpointEvent",
    "CheckpointResponseOptions",
    "TrackEvent",
    "CheckpointResponse",
    "Verification",
    "ApiError",
    "VerificationStatus",
    "VerificationOutcome",
    "ComposerException",
    "ComposerMissingParameterError",
    "ComposerMissingConfigError",
    "ComposerInvalidConfigError",
]
