# Error Handling & Resilience Guide

## Overview

This guide explains the error handling and resilience patterns implemented in MeetingActions to handle failures gracefully and protect against cascading failures.

## Components

### 1. Custom Exception Hierarchy

Located in: `src/core/base/exceptions.py`

All custom exceptions inherit from `MeetingActionsError` and provide structured error information.

```python
from src.core.base.exceptions import (
    AgentError,
    AgentTimeoutError,
    WorkflowError,
    ExternalServiceError
)

# Raise specific exception
raise AgentTimeoutError(
    message="Agent did not respond in time",
    error_code="AGENT_TIMEOUT",
    context={
        "agent_url": "http://jira-agent:8000",
        "timeout": 120
    }
)
```

#### Exception Categories

```
MeetingActionsError (base)
├── AgentError
│   ├── AgentTimeoutError
│   ├── AgentUnavailableError
│   ├── AgentResponseError
│   └── AgentAuthenticationError
├── WorkflowError
│   ├── WorkflowValidationError
│   ├── WorkflowExecutionError
│   └── WorkflowTimeoutError
├── ExternalServiceError
│   ├── GoogleAPIError
│   ├── JiraAPIError
│   └── LLMError
├── InfrastructureError
│   ├── CacheError
│   ├── RegistryError
│   └── ConfigurationError
└── CircuitBreakerError
    └── CircuitOpenError
```

### 2. Retry Decorator

Located in: `src/core/base/retry.py`

Automatically retries failed operations with configurable backoff strategies.

#### Basic Usage

```python
from src.core.base.error_handler import with_retry, BackoffStrategy

@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL_JITTER,
    base_delay=1.0,
    max_delay=30.0
)
async def fetch_data(url: str):
    """Fetch data with automatic retry."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

#### Backoff Strategies

1. **CONSTANT**: Fixed delay between retries
   ```python
   @with_retry(backoff=BackoffStrategy.CONSTANT, base_delay=2.0)
   # Delays: 2s, 2s, 2s
   ```

2. **LINEAR**: Linearly increasing delay
   ```python
   @with_retry(backoff=BackoffStrategy.LINEAR, base_delay=1.0)
   # Delays: 1s, 2s, 3s
   ```

3. **EXPONENTIAL**: Exponentially increasing delay
   ```python
   @with_retry(backoff=BackoffStrategy.EXPONENTIAL, base_delay=1.0)
   # Delays: 1s, 2s, 4s, 8s, 16s
   ```

4. **EXPONENTIAL_JITTER** (Recommended): Exponential with randomness
   ```python
   @with_retry(backoff=BackoffStrategy.EXPONENTIAL_JITTER, base_delay=1.0)
   # Delays: 1.05s, 2.13s, 4.07s (with 10% jitter)
   # Prevents thundering herd problem
   ```

#### Retry Specific Exceptions

```python
import httpx
from src.core.base.error_handler import with_retry

@with_retry(
    max_attempts=5,
    retryable_exceptions=(
        httpx.TimeoutException,
        httpx.NetworkError,
        ConnectionError
    )
)
async def call_api(url: str):
    """Only retries on network-related errors."""
    # Other exceptions will not be retried
    pass
```

#### Retry Callbacks

```python
def on_retry_callback(error: Exception, attempt: int):
    """Called before each retry."""
    logger.warning(f"Retry attempt {attempt}: {error}")
    # Send metric, alert, etc.

@with_retry(max_attempts=3, on_retry=on_retry_callback)
async def operation():
    pass
```

### 3. Circuit Breaker Pattern

Located in: `src/core/base/circuit_breaker.py`

Protects your system from cascading failures by "opening" after too many failures.

#### How It Works

```
┌─────────────┐
│   CLOSED    │ ──> Normal operation, requests pass through
│ (Normal)    │
└──────┬──────┘
       │ Too many failures
       ▼
┌─────────────┐
│    OPEN     │ ──> Requests blocked, fail fast
│  (Failing)  │
└──────┬──────┘
       │ Timeout expires
       ▼
┌─────────────┐
│ HALF_OPEN   │ ──> Testing recovery, limited requests
│  (Testing)  │
└──────┬──────┘
       │
       ├──> Success ──> Back to CLOSED
       └──> Failure ──> Back to OPEN
```

#### Basic Usage

```python
from src.core.base.error_handler import with_circuit_breaker

@with_circuit_breaker(
    name="google_api",
    failure_threshold=5,      # Open after 5 failures
    recovery_timeout=60.0,    # Try recovery after 60s
    success_threshold=2       # Need 2 successes to close
)
async def call_google_api(endpoint: str):
    """Protected by circuit breaker."""
    response = await httpx.get(f"https://api.google.com/{endpoint}")
    return response.json()
```

#### Circuit Breaker States

**CLOSED (Normal)**
- All requests pass through
- Failures increment counter
- Opens if threshold exceeded

**OPEN (Failing)**
- All requests immediately fail with `CircuitOpenError`
- No actual calls made (fail fast)
- Transitions to HALF_OPEN after timeout

**HALF_OPEN (Testing)**
- Limited requests allowed to test recovery
- Single failure → back to OPEN
- Multiple successes → back to CLOSED

#### Manual Circuit Control

```python
from src.core.base.error_handler import get_circuit_breaker

# Get circuit breaker
circuit = get_circuit_breaker("google_api")

# Check state
if circuit.state == CircuitState.OPEN:
    logger.error("Circuit is open!")

# Get statistics
stats = circuit.get_stats()
# {
#     "name": "google_api",
#     "state": "open",
#     "failure_count": 5,
#     "failure_threshold": 5,
#     "recovery_timeout": 60.0,
#     "last_failure_time": 1234567890.0
# }

# Manually reset circuit
circuit.reset()
```

#### Monitoring All Circuits

```python
from src.core.base.circuit_breaker import get_all_circuit_breakers

circuits = get_all_circuit_breakers()

for name, breaker in circuits.items():
    stats = breaker.get_stats()
    print(f"{name}: {stats['state']} ({stats['failure_count']} failures)")
```

### 4. Error Context Manager

Located in: `src/core/base/error_handler.py`

Automatically enriches errors with contextual information.

#### Usage

```python
from src.core.base.error_handler import ErrorContext

async def process_meeting(meeting_id: str, user_id: str):
    """Process meeting with error context."""

    async with ErrorContext(
        "process_meeting",
        meeting_id=meeting_id,
        user_id=user_id
    ):
        # Any errors here will include:
        # - operation: "process_meeting"
        # - meeting_id: value
        # - user_id: value

        result = await fetch_meeting_data(meeting_id)
        items = await generate_action_items(result)

        return items
```

When an error occurs:
```python
# Error will have context automatically:
{
    "error": "GoogleAPIError",
    "message": "Failed to fetch document",
    "context": {
        "operation": "process_meeting",
        "meeting_id": "meeting-123",
        "user_id": "user@example.com"
    }
}
```

### 5. Combining Patterns

#### Retry + Circuit Breaker

```python
from src.core.base.error_handler import (
    with_retry,
    with_circuit_breaker,
    BackoffStrategy
)

@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL_JITTER
)
@with_circuit_breaker(
    name="jira_api",
    failure_threshold=5,
    recovery_timeout=60.0
)
async def call_jira_api(endpoint: str):
    """
    Resilience layers:
    1. Circuit breaker checks if circuit is open (fail fast)
    2. If closed/half-open, makes request
    3. On failure, retry logic kicks in (3 attempts)
    4. Repeated failures increment circuit breaker counter
    5. After threshold, circuit opens
    """
    response = await httpx.post(
        f"https://jira.example.com/api/{endpoint}"
    )
    return response.json()
```

#### Retry + Circuit Breaker + Error Context

```python
async def dispatch_action_item(item: dict, agent_url: str):
    """Full error handling stack."""

    async with ErrorContext(
        "dispatch_action_item",
        item_title=item["title"],
        agent_url=agent_url
    ):
        result = await _dispatch_with_resilience(item, agent_url)
        return result


@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL_JITTER,
    base_delay=2.0
)
@with_circuit_breaker(
    name="agent_dispatch",
    failure_threshold=5,
    recovery_timeout=60.0
)
async def _dispatch_with_resilience(item: dict, agent_url: str):
    """Internal dispatch with retry and circuit breaker."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{agent_url}/agent",
            json={"query": format_query(item)}
        )
        response.raise_for_status()
        return response.json()
```

## Best Practices

### 1. Use Specific Exceptions

❌ **Bad:**
```python
raise Exception("Agent failed")
```

✅ **Good:**
```python
raise AgentUnavailableError(
    message="Agent is unavailable",
    error_code="AGENT_UNAVAILABLE",
    context={"agent_url": url, "status_code": 503}
)
```

### 2. Set Appropriate Retry Limits

```python
# Different operations need different retry strategies

# Quick, non-critical operations
@with_retry(max_attempts=2, base_delay=0.5)
async def fetch_cache():
    pass

# Important external API calls
@with_retry(max_attempts=5, base_delay=2.0, max_delay=30.0)
async def create_jira_ticket():
    pass

# Critical user-facing operations
@with_retry(max_attempts=3, base_delay=1.0)
@with_circuit_breaker(failure_threshold=3)
async def process_user_request():
    pass
```

### 3. Use Circuit Breakers for External Services

```python
# Each external service should have its own circuit breaker

@with_circuit_breaker(name="google_docs", failure_threshold=5)
async def call_google_docs():
    pass

@with_circuit_breaker(name="jira_api", failure_threshold=3)
async def call_jira():
    pass

@with_circuit_breaker(name="llm_api", failure_threshold=10)
async def call_llm():
    pass
```

### 4. Add Error Context to Operations

```python
async def complex_workflow(meeting_id: str):
    """Add context at each level."""

    # Top-level context
    async with ErrorContext("complex_workflow", meeting_id=meeting_id):

        # Step 1
        async with ErrorContext("fetch_documents"):
            docs = await fetch_documents(meeting_id)

        # Step 2
        async with ErrorContext("generate_items", doc_count=len(docs)):
            items = await generate_action_items(docs)

        # Step 3
        async with ErrorContext("dispatch_items", item_count=len(items)):
            results = await dispatch_items(items)

        return results
```

### 5. Monitor Circuit Breaker Health

```python
# Add health check endpoint
from fastapi import FastAPI
from src.core.base.circuit_breaker import get_all_circuit_breakers

app = FastAPI()

@app.get("/health/circuit-breakers")
async def circuit_breaker_health():
    """Check circuit breaker health."""
    breakers = get_all_circuit_breakers()

    health = {
        "healthy": True,
        "circuits": {}
    }

    for name, breaker in breakers.items():
        stats = breaker.get_stats()
        health["circuits"][name] = stats

        if stats["state"] == "open":
            health["healthy"] = False

    return health
```

## FastAPI Integration

### Error Handler Middleware

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from src.core.base.error_handler import handle_error_response
from src.core.base.exceptions import MeetingActionsError

app = FastAPI()

@app.exception_handler(MeetingActionsError)
async def meeting_actions_error_handler(
    request: Request,
    exc: MeetingActionsError
):
    """Handle custom exceptions."""
    http_exc = handle_error_response(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail
    )
```

### Using in Endpoints

```python
from fastapi import HTTPException
from src.core.base.error_handler import (
    with_retry,
    with_circuit_breaker,
    ErrorContext
)

@app.post("/generate")
async def generate_action_items(meeting_id: str):
    """Generate action items with error handling."""

    async with ErrorContext("generate_action_items", meeting_id=meeting_id):
        # Automatically handled by exception middleware
        result = await _generate_with_resilience(meeting_id)
        return result


@with_retry(max_attempts=3)
@with_circuit_breaker(name="generation_workflow")
async def _generate_with_resilience(meeting_id: str):
    """Internal implementation with resilience."""
    # Implementation here
    pass
```

## Testing Error Handling

### Testing Retry Logic

```python
import pytest
from src.core.base.error_handler import with_retry
from src.core.base.exceptions import MaxRetriesExceededError

@pytest.mark.asyncio
async def test_retry_eventually_succeeds():
    """Test retry succeeds after initial failures."""
    call_count = 0

    @with_retry(max_attempts=3)
    async def flaky_function():
        nonlocal call_count
        call_count += 1

        if call_count < 3:
            raise ConnectionError("Temporary failure")

        return "success"

    result = await flaky_function()
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_max_attempts_exceeded():
    """Test max retries exceeded."""

    @with_retry(max_attempts=3)
    async def always_fails():
        raise ConnectionError("Permanent failure")

    with pytest.raises(MaxRetriesExceededError) as exc_info:
        await always_fails()

    assert exc_info.value.attempts == 3
```

### Testing Circuit Breaker

```python
import pytest
from src.core.base.error_handler import with_circuit_breaker
from src.core.base.exceptions import CircuitOpenError

@pytest.mark.asyncio
async def test_circuit_opens_after_failures():
    """Test circuit opens after threshold."""
    call_count = 0

    @with_circuit_breaker(
        name="test_circuit",
        failure_threshold=3,
        recovery_timeout=60.0
    )
    async def failing_function():
        nonlocal call_count
        call_count += 1
        raise Exception("Failure")

    # First 3 calls should fail normally
    for _ in range(3):
        with pytest.raises(Exception):
            await failing_function()

    # 4th call should fail with CircuitOpenError
    with pytest.raises(CircuitOpenError):
        await failing_function()

    assert call_count == 3  # Circuit opened, no more actual calls
```

## Migration Guide

### Before (No Error Handling)

```python
async def dispatch_to_agent(item: dict, agent_url: str):
    """Old code - no error handling."""
    response = requests.post(f"{agent_url}/agent", json=item)
    return response.json()
```

### After (With Error Handling)

```python
from src.core.base.error_handler import (
    with_retry,
    with_circuit_breaker,
    ErrorContext,
    AgentTimeoutError,
    AgentUnavailableError
)

@with_retry(max_attempts=3, backoff=BackoffStrategy.EXPONENTIAL_JITTER)
@with_circuit_breaker(name="agent_dispatch", failure_threshold=5)
async def dispatch_to_agent(item: dict, agent_url: str):
    """New code - comprehensive error handling."""

    async with ErrorContext(
        "dispatch_to_agent",
        item_title=item.get("title"),
        agent_url=agent_url
    ):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{agent_url}/agent",
                    json={"query": format_query(item)}
                )

                if response.status_code >= 500:
                    raise AgentUnavailableError(
                        message=f"Agent unavailable: {response.status_code}",
                        context={"agent_url": agent_url}
                    )

                response.raise_for_status()
                return response.json()

        except httpx.TimeoutException as e:
            raise AgentTimeoutError(
                message="Agent timeout",
                context={"agent_url": agent_url, "timeout": 120.0},
                cause=e
            )
```

## Summary

The error handling system provides:

✅ **Retry Logic**: Automatic retry with exponential backoff
✅ **Circuit Breakers**: Protect against cascading failures
✅ **Error Context**: Automatic error enrichment
✅ **Type Safety**: Structured exception hierarchy
✅ **Observability**: Comprehensive logging and monitoring
✅ **Testing**: Easy to test with mocks and fixtures

Use these patterns consistently across the codebase for robust, production-ready error handling.
