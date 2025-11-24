"""Retry decorator with configurable backoff strategies.

Provides retry logic for handling transient failures in distributed systems.
"""

# pylint: disable=import-error,no-name-in-module

import asyncio
import functools
import random
import time
from enum import Enum
from typing import Callable, Optional, Tuple, Type, Union

from src.infrastructure.logging.logging_config import get_logger
from src.shared.resilience.exceptions import MaxRetriesExceededError, RetryableError

logger = get_logger("retry")


class BackoffStrategy(str, Enum):
    """Backoff strategy for retries."""

    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    EXPONENTIAL_JITTER = "exponential_jitter"


def exponential_backoff(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0
) -> float:
    """Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (2**attempt), max_delay)
    return delay


def exponential_backoff_with_jitter(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0
) -> float:
    """Calculate exponential backoff with jitter.

    Adds randomness to prevent thundering herd problem.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds with jitter
    """
    delay = exponential_backoff(attempt, base_delay, max_delay)
    jitter = random.uniform(0, delay * 0.1)  # Add up to 10% jitter
    return delay + jitter


def linear_backoff(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0
) -> float:
    """Calculate linear backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (attempt + 1), max_delay)
    return delay


def constant_backoff(
    _attempt: int, base_delay: float = 1.0, _max_delay: float = 60.0
) -> float:
    """Calculate constant backoff delay.

    Args:
        _attempt: Current attempt number (0-indexed, unused)
        base_delay: Constant delay in seconds
        _max_delay: Maximum delay in seconds (unused)
        max_delay: Not used for constant backoff

    Returns:
        Constant delay in seconds
    """
    return base_delay


def get_backoff_function(
    strategy: BackoffStrategy,
) -> Callable[[int, float, float], float]:
    """Get backoff function for strategy.

    Args:
        strategy: Backoff strategy to use

    Returns:
        Backoff function
    """
    strategies = {
        BackoffStrategy.CONSTANT: constant_backoff,
        BackoffStrategy.LINEAR: linear_backoff,
        BackoffStrategy.EXPONENTIAL: exponential_backoff,
        BackoffStrategy.EXPONENTIAL_JITTER: exponential_backoff_with_jitter,
    }
    return strategies[strategy]


# pylint: disable=too-many-arguments,too-many-positional-arguments
def with_retry(
    max_attempts: int = 3,
    backoff: Union[BackoffStrategy, str] = BackoffStrategy.EXPONENTIAL_JITTER,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
):
    """Decorator to retry function on failure with backoff.

    Args:
        max_attempts: Maximum number of attempts (including initial)
        backoff: Backoff strategy to use
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: Tuple of exception types to retry on.
            If None, retries on all exceptions.
        on_retry: Optional callback called before each retry.
            Receives (exception, attempt_number).

    Returns:
        Decorated function

    Example:
        @with_retry(max_attempts=3, backoff=BackoffStrategy.EXPONENTIAL)
        async def call_external_api(url: str):
            response = await httpx.get(url)
            return response.json()
    """
    if isinstance(backoff, str):
        backoff = BackoffStrategy(backoff)

    backoff_fn = get_backoff_function(backoff)

    # Default to retrying on common transient errors
    if retryable_exceptions is None:
        retryable_exceptions = (
            RetryableError,
            TimeoutError,
            ConnectionError,
            asyncio.TimeoutError,
        )

    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Async wrapper with retry logic."""
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt + 1}"
                        )
                    return result

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise MaxRetriesExceededError(
                            message=(
                                f"Max retries ({max_attempts}) exceeded "
                                f"for {func.__name__}"
                            ),
                            attempts=max_attempts,
                            last_error=e,
                            context={
                                "function": func.__name__,
                                "args": str(args)[:100],
                                "kwargs": str(kwargs)[:100],
                            },
                        ) from e

                    # Calculate delay and wait
                    delay = backoff_fn(attempt, base_delay, max_delay)

                    logger.warning(
                        f"{func.__name__} failed on attempt "
                        f"{attempt + 1}/{max_attempts}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")

                    await asyncio.sleep(delay)

            # Should never reach here, but just in case
            raise MaxRetriesExceededError(
                message=f"Max retries ({max_attempts}) exceeded for {func.__name__}",
                attempts=max_attempts,
                last_error=last_exception,
            )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            """Sync wrapper with retry logic."""
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt + 1}"
                        )
                    return result

                except retryable_exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise MaxRetriesExceededError(
                            message=(
                                f"Max retries ({max_attempts}) exceeded "
                                f"for {func.__name__}"
                            ),
                            attempts=max_attempts,
                            last_error=e,
                            context={
                                "function": func.__name__,
                                "args": str(args)[:100],
                                "kwargs": str(kwargs)[:100],
                            },
                        ) from e

                    # Calculate delay and wait
                    delay = backoff_fn(attempt, base_delay, max_delay)

                    logger.warning(
                        f"{func.__name__} failed on attempt "
                        f"{attempt + 1}/{max_attempts}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )

                    # Call retry callback if provided
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            logger.error(f"Error in retry callback: {callback_error}")

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise MaxRetriesExceededError(
                message=f"Max retries ({max_attempts}) exceeded for {func.__name__}",
                attempts=max_attempts,
                last_error=last_exception,
            )

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
