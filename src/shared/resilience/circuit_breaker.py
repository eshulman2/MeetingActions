"""Circuit Breaker pattern implementation.

Protects system from cascading failures by stopping requests to failing services.
"""

# pylint: disable=import-error,no-name-in-module

import asyncio
import functools
import time
from enum import Enum
from typing import Callable, Optional, Tuple, Type

from src.infrastructure.logging.logging_config import get_logger
from src.shared.resilience.exceptions import CircuitOpenError

logger = get_logger("circuit_breaker")


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Too many failures, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are blocked
    - HALF_OPEN: Testing recovery, limited requests allowed

    Attributes:
        name: Name of the circuit breaker
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds before trying half-open state
        expected_exception: Exception type that counts as failure
    """

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        success_threshold: int = 2,
    ):
        """Initialize circuit breaker.

        Args:
            name: Name for this circuit breaker
            failure_threshold: Consecutive failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type to count as failure
            success_threshold: Successes needed in half-open to close circuit
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._failure_count

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False

        return (time.time() - self._last_failure_time) >= self.recovery_timeout

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function

        Returns:
            Result from function

        Raises:
            CircuitOpenError: If circuit is open
            Exception: Original exception from function
        """
        async with self._lock:
            # Check if circuit should transition to half-open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(
                        f"Circuit breaker '{self.name}' transitioning to HALF_OPEN"
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    last_failure = self._last_failure_time or time.time()
                    retry_after = int(
                        self.recovery_timeout - (time.time() - last_failure)
                    )
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN, "
                        f"retry after {retry_after}s"
                    )
                    raise CircuitOpenError(
                        message=f"Circuit breaker '{self.name}' is OPEN",
                        error_code="CIRCUIT_OPEN",
                        context={
                            "circuit_name": self.name,
                            "state": self._state,
                            "failure_count": self._failure_count,
                        },
                        retry_after=retry_after,
                    )

        # Execute function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # Record success
            await self._on_success()
            return result

        except self.expected_exception:
            # Record failure
            await self._on_failure()
            raise

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"Circuit breaker '{self.name}' success in HALF_OPEN state "
                    f"({self._success_count}/{self.success_threshold})"
                )

                if self._success_count >= self.success_threshold:
                    logger.info(
                        f"Circuit breaker '{self.name}' transitioning to CLOSED"
                    )
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            logger.warning(
                f"Circuit breaker '{self.name}' failure "
                f"({self._failure_count}/{self.failure_threshold})"
            )

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open immediately opens circuit
                logger.warning(
                    f"Circuit breaker '{self.name}' transitioning to OPEN "
                    f"(failure in HALF_OPEN state)"
                )
                self._state = CircuitState.OPEN
                self._success_count = 0

            elif self._failure_count >= self.failure_threshold:
                # Too many failures, open circuit
                logger.error(
                    f"Circuit breaker '{self.name}' transitioning to OPEN "
                    f"(threshold {self.failure_threshold} exceeded)"
                )
                self._state = CircuitState.OPEN

    def reset(self):
        """Manually reset circuit breaker to closed state."""
        logger.info(f"Manually resetting circuit breaker '{self.name}'")
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None

    def get_stats(self) -> dict:
        """Get circuit breaker statistics.

        Returns:
            Dictionary with circuit breaker stats
        """
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }


# Global registry of circuit breakers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception,
    success_threshold: int = 2,
) -> CircuitBreaker:
    """Get or create circuit breaker by name.

    Args:
        name: Name of circuit breaker
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        expected_exception: Exception type to count as failure
        success_threshold: Successes needed to close circuit

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            success_threshold=success_threshold,
        )

    return _circuit_breakers[name]


def with_circuit_breaker(
    name: Optional[str] = None,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Tuple[Type[Exception], ...] = (Exception,),
    success_threshold: int = 2,
):
    """Decorator to protect function with circuit breaker.

    Args:
        name: Circuit breaker name (defaults to function name)
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before attempting recovery
        expected_exception: Exception types to count as failure
        success_threshold: Successes needed to close circuit

    Returns:
        Decorated function

    Example:
        @with_circuit_breaker(failure_threshold=3, recovery_timeout=30)
        async def call_external_api(url: str):
            response = await httpx.get(url)
            return response.json()
    """

    def decorator(func: Callable):
        circuit_name = name or f"{func.__module__}.{func.__name__}"
        circuit = get_circuit_breaker(
            name=circuit_name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=(
                expected_exception[0] if expected_exception else Exception
            ),
            success_threshold=success_threshold,
        )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            """Async wrapper with circuit breaker."""
            return await circuit.call(func, *args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            """Sync wrapper with circuit breaker."""
            # For sync functions, we need to run in event loop
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(circuit.call(func, *args, **kwargs))

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def get_all_circuit_breakers() -> dict[str, CircuitBreaker]:
    """Get all registered circuit breakers.

    Returns:
        Dictionary mapping names to circuit breakers
    """
    return _circuit_breakers.copy()


def reset_all_circuit_breakers():
    """Reset all circuit breakers to closed state."""
    for circuit in _circuit_breakers.values():
        circuit.reset()
