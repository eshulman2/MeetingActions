"""Centralized error handling for MeetingActions platform.

Provides unified error handling, retry logic, and circuit breaker patterns.
"""

# pylint: disable=wildcard-import,import-error,no-name-in-module

import traceback
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from src.core.base.circuit_breaker import (  # noqa: F401
    CircuitBreaker,
    CircuitState,
    get_circuit_breaker,
    with_circuit_breaker,
)
from src.core.base.exceptions import *  # noqa: F401, F403
from src.core.base.exceptions import (
    AgentAuthenticationError,
    AgentError,
    AgentResponseError,
    AgentTimeoutError,
    AgentUnavailableError,
    CacheError,
    CircuitBreakerError,
    CircuitOpenError,
    ConfigurationError,
    ExternalServiceError,
    GoogleAPIError,
    InfrastructureError,
    JiraAPIError,
    LLMError,
    MaxRetriesExceededError,
    MeetingActionsError,
    RegistryError,
    RetryableError,
    WorkflowError,
    WorkflowExecutionError,
    WorkflowTimeoutError,
    WorkflowValidationError,
)

# Re-export for convenience
from src.core.base.retry import BackoffStrategy, with_retry  # noqa: F401
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("error_handler")

# Define public API - re-export all exceptions and utilities
__all__ = [
    # Core error handling
    "ErrorContext",
    "handle_error_response",
    "safe_execute",
    "safe_execute_async",
    # Base exceptions
    "MeetingActionsError",
    "AgentError",
    "WorkflowError",
    "ExternalServiceError",
    "InfrastructureError",
    "CircuitBreakerError",
    "RetryableError",
    # Agent exceptions
    "AgentTimeoutError",
    "AgentUnavailableError",
    "AgentResponseError",
    "AgentAuthenticationError",
    # Workflow exceptions
    "WorkflowValidationError",
    "WorkflowExecutionError",
    "WorkflowTimeoutError",
    # External service exceptions
    "GoogleAPIError",
    "JiraAPIError",
    "LLMError",
    # Infrastructure exceptions
    "CacheError",
    "RegistryError",
    "ConfigurationError",
    # Circuit breaker
    "CircuitOpenError",
    "CircuitBreaker",
    "CircuitState",
    "get_circuit_breaker",
    "with_circuit_breaker",
    # Retry exceptions
    "MaxRetriesExceededError",
    "BackoffStrategy",
    "with_retry",
]


class ErrorContext:
    """Context manager for error handling with automatic logging and enrichment.

    Usage:
        async with ErrorContext("process_action_items", user_id="user123"):
            result = await process_action_items()
    """

    def __init__(self, operation: str, **context: Any):
        """Initialize error context.

        Args:
            operation: Name of operation being performed
            **context: Additional context to include in errors
        """
        self.operation = operation
        self.context = context

    async def __aenter__(self):
        """Enter async context."""
        logger.debug(
            f"Starting operation: {self.operation}", extra={"context": self.context}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context and handle errors."""
        if exc_type is None:
            logger.debug(
                f"Operation completed: {self.operation}",
                extra={"context": self.context},
            )
            return False

        # Error occurred
        if isinstance(exc_val, MeetingActionsError):
            # Already our custom exception, enrich it
            exc_val.context.update(self.context)
            exc_val.context["operation"] = self.operation
        else:
            # Wrap in our exception
            logger.error(
                f"Unexpected error in {self.operation}: {exc_val}",
                extra={
                    "context": self.context,
                    "exc_type": exc_type.__name__,
                    "traceback": traceback.format_exc(),
                },
            )

        # Don't suppress exception
        return False

    def __enter__(self):
        """Enter sync context."""
        logger.debug(
            f"Starting operation: {self.operation}", extra={"context": self.context}
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit sync context and handle errors."""
        if exc_type is None:
            logger.debug(
                f"Operation completed: {self.operation}",
                extra={"context": self.context},
            )
            return False

        # Error occurred
        if isinstance(exc_val, MeetingActionsError):
            # Already our custom exception, enrich it
            exc_val.context.update(self.context)
            exc_val.context["operation"] = self.operation
        else:
            # Log unexpected error
            logger.error(
                f"Unexpected error in {self.operation}: {exc_val}",
                extra={
                    "context": self.context,
                    "exc_type": exc_type.__name__,
                    "traceback": traceback.format_exc(),
                },
            )

        # Don't suppress exception
        return False


def handle_error_response(
    error: Exception, default_status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
) -> HTTPException:
    """Convert exception to HTTPException for FastAPI.

    Args:
        error: Exception to convert
        default_status_code: Default HTTP status code

    Returns:
        HTTPException with appropriate status and detail
    """
    # Handle circuit breaker errors
    if isinstance(error, CircuitOpenError):
        headers = {}
        if error.retry_after:
            headers["Retry-After"] = str(error.retry_after)

        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error.to_dict(),
            headers=headers,
        )

    # Handle max retries exceeded
    if isinstance(error, MaxRetriesExceededError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error.to_dict()
        )

    # Handle agent errors
    if isinstance(error, AgentError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=error.to_dict()
        )

    # Handle workflow errors
    if isinstance(error, WorkflowError):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error.to_dict()
        )

    # Handle external service errors
    if isinstance(error, ExternalServiceError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=error.to_dict()
        )

    # Handle our custom errors
    if isinstance(error, MeetingActionsError):
        return HTTPException(status_code=default_status_code, detail=error.to_dict())

    # Handle generic errors
    logger.error(
        f"Unhandled error: {error}", extra={"traceback": traceback.format_exc()}
    )

    return HTTPException(
        status_code=default_status_code,
        detail={
            "error": error.__class__.__name__,
            "message": str(error),
        },
    )


def safe_execute(
    func,
    *args,
    error_context: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = True,
    **kwargs,
):
    """Execute function with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments
        error_context: Additional context for errors
        raise_on_error: Whether to raise exception or return None
        **kwargs: Keyword arguments

    Returns:
        Function result or None on error

    Raises:
        Exception: If raise_on_error is True
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(
            f"Error executing {func.__name__}: {e}",
            extra={
                "error_context": error_context or {},
                "traceback": traceback.format_exc(),
            },
        )

        if raise_on_error:
            raise
        return None


async def safe_execute_async(
    func,
    *args,
    error_context: Optional[Dict[str, Any]] = None,
    raise_on_error: bool = True,
    **kwargs,
):
    """Execute async function with error handling.

    Args:
        func: Async function to execute
        *args: Positional arguments
        error_context: Additional context for errors
        raise_on_error: Whether to raise exception or return None
        **kwargs: Keyword arguments

    Returns:
        Function result or None on error

    Raises:
        Exception: If raise_on_error is True
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        logger.error(
            f"Error executing {func.__name__}: {e}",
            extra={
                "error_context": error_context or {},
                "traceback": traceback.format_exc(),
            },
        )

        if raise_on_error:
            raise
        return None
