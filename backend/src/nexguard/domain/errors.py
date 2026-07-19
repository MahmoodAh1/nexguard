"""Domain error hierarchy.

These are raised by domain and application code and translated to transport-level
responses (RFC-9457 ``problem+json``) at the interface boundary. They never carry
framework types.
"""

from __future__ import annotations


class NexGuardError(Exception):
    """Base class for all domain/application errors."""


class ValidationError(NexGuardError):
    """An input violated a domain invariant."""


class NotFoundError(NexGuardError):
    """A referenced entity does not exist."""

    def __init__(self, entity: str, identifier: object) -> None:
        super().__init__(f"{entity} '{identifier}' not found")
        self.entity = entity
        self.identifier = identifier


class AuthenticationError(NexGuardError):
    """Credentials were missing or invalid."""


class AuthorizationError(NexGuardError):
    """The caller is authenticated but lacks the required role/permission."""


class RateLimitError(NexGuardError):
    """The caller exceeded the allowed request rate."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class DetectionError(NexGuardError):
    """A detector failed to produce a verdict (e.g. model not loaded)."""


class ReportGenerationError(NexGuardError):
    """The LLM triage copilot failed to produce a usable report."""


class ReportRejectedError(NexGuardError):
    """A generated report failed verification and was rejected.

    This is a *safety success*, not a bug: the verifier refused a report that
    referenced evidence which does not exist.
    """

    def __init__(self, reasons: list[str]) -> None:
        super().__init__("incident report rejected by verifier: " + "; ".join(reasons))
        self.reasons = reasons
