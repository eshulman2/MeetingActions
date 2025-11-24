"""Custom exceptions for MeetingActions platform.

Provides a hierarchy of exceptions for better error handling and debugging.
"""

from typing import Any, Dict, Optional


class MeetingActionsError(Exception):
    """Base exception for all MeetingActions errors.

    All custom exceptions should inherit from this class.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        """Initialize error with context.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code (e.g., "AGENT_TIMEOUT")
            context: Additional context about the error
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
        }


# Agent Exceptions


class AgentError(MeetingActionsError):
    """Base exception for agent-related errors."""


class AgentTimeoutError(AgentError):
    """Raised when agent operation times out."""


class AgentUnavailableError(AgentError):
    """Raised when agent is unavailable or unhealthy."""


class AgentResponseError(AgentError):
    """Raised when agent returns invalid response."""


class AgentAuthenticationError(AgentError):
    """Raised when agent authentication fails."""


# Workflow Exceptions


class WorkflowError(MeetingActionsError):
    """Base exception for workflow-related errors."""


class WorkflowValidationError(WorkflowError):
    """Raised when workflow input validation fails."""


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails."""


class WorkflowTimeoutError(WorkflowError):
    """Raised when workflow execution times out."""


# External Service Exceptions


class ExternalServiceError(MeetingActionsError):
    """Base exception for external service errors."""


class GoogleAPIError(ExternalServiceError):
    """Raised when Google API call fails."""


class JiraAPIError(ExternalServiceError):
    """Raised when Jira API call fails."""


class LLMError(ExternalServiceError):
    """Raised when LLM API call fails."""


# Infrastructure Exceptions


class InfrastructureError(MeetingActionsError):
    """Base exception for infrastructure-related errors."""


class CacheError(InfrastructureError):
    """Raised when cache operation fails."""


class RegistryError(InfrastructureError):
    """Raised when registry operation fails."""


class ConfigurationError(InfrastructureError):
    """Raised when configuration is invalid."""


# Circuit Breaker Exceptions


class CircuitBreakerError(MeetingActionsError):
    """Base exception for circuit breaker errors."""


class CircuitOpenError(CircuitBreakerError):
    """Raised when circuit is open and request is rejected."""

    def __init__(
        self,
        message: str = "Circuit breaker is OPEN - too many failures",
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


# Retry Exceptions


class RetryableError(MeetingActionsError):
    """Base exception for errors that can be retried."""


class MaxRetriesExceededError(MeetingActionsError):
    """Raised when maximum retry attempts are exceeded."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_error: Optional[Exception] = None,
        **kwargs
    ):
        super().__init__(message, **kwargs)
        self.attempts = attempts
        self.last_error = last_error
