"""Example integration of error handling components.

This file demonstrates how to use the error handling utilities
in real-world scenarios like agent dispatch workflows.
"""

# pylint: disable=import-error,no-name-in-module

import asyncio
from typing import Any, Dict

import httpx

from src.core.error_handler import (
    AgentResponseError,
    AgentTimeoutError,
    AgentUnavailableError,
    BackoffStrategy,
    ErrorContext,
    with_circuit_breaker,
    with_retry,
)
from src.infrastructure.logging.logging_config import get_logger
from src.shared.resilience.circuit_breaker import get_all_circuit_breakers

logger = get_logger("error_handling_example")


# Example 1: Simple retry with exponential backoff
@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL_JITTER,
    base_delay=1.0,
    max_delay=10.0,
)
async def fetch_document(doc_id: str) -> Dict[str, Any]:
    """Fetch document with automatic retry on failure.

    Retries up to 3 times with exponential backoff + jitter.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.example.com/docs/{doc_id}", timeout=10.0
        )
        response.raise_for_status()
        return response.json()


# Example 2: Circuit breaker for external service
@with_circuit_breaker(
    name="google_docs_api",
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=2,
)
async def call_google_docs_api(endpoint: str, **kwargs) -> Dict[str, Any]:
    """Call Google Docs API with circuit breaker protection.

    After 5 failures, circuit opens and blocks requests for 60 seconds.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://docs.googleapis.com/v1/{endpoint}", **kwargs
        )
        response.raise_for_status()
        return response.json()


# Example 3: Combined retry + circuit breaker
@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL,
    retryable_exceptions=(httpx.TimeoutException, httpx.NetworkError),
)
@with_circuit_breaker(name="jira_api", failure_threshold=3, recovery_timeout=30.0)
async def call_jira_api(endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
    """Call Jira API with both retry and circuit breaker.

    - Retries on timeout/network errors (3 attempts)
    - Circuit breaker opens after 3 failures
    - Combines resilience patterns for maximum reliability
    """
    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(
                f"https://jira.example.com/rest/api/2/{endpoint}", **kwargs
            )
        else:
            response = await client.post(
                f"https://jira.example.com/rest/api/2/{endpoint}", **kwargs
            )

        response.raise_for_status()
        return response.json()


# Example 4: Error context for enrichment
async def process_action_item_with_context(
    action_item: Dict[str, Any], agent_url: str
) -> Dict[str, Any]:
    """Process action item with error context.

    Error context automatically enriches exceptions with metadata.
    """
    async with ErrorContext(
        "process_action_item",
        action_item_title=action_item.get("title"),
        agent_url=agent_url,
    ):
        # Any errors here will include the context
        result = await dispatch_to_agent(action_item, agent_url)
        return result


# Example 5: Agent dispatch with full error handling
@with_retry(
    max_attempts=3,
    backoff=BackoffStrategy.EXPONENTIAL_JITTER,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=(
        httpx.TimeoutException,
        httpx.NetworkError,
        AgentTimeoutError,
    ),
)
@with_circuit_breaker(name="agent_dispatch", failure_threshold=5, recovery_timeout=60.0)
async def dispatch_to_agent(
    action_item: Dict[str, Any], agent_url: str, timeout: float = 120.0
) -> Dict[str, Any]:
    """Dispatch action item to agent with comprehensive error handling.

    Features:
    - Automatic retry on transient failures (3 attempts)
    - Circuit breaker protection (5 failures triggers open)
    - Proper timeout handling
    - Type-specific exceptions
    """
    logger.info(
        f"Dispatching action item to {agent_url}",
        extra={"action_item": action_item.get("title")},
    )

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{agent_url}/agent", json={"query": format_query(action_item)}
            )

            # Check response status
            if response.status_code >= 500:
                raise AgentUnavailableError(
                    message=f"Agent at {agent_url} is unavailable",
                    error_code="AGENT_UNAVAILABLE",
                    context={
                        "status_code": response.status_code,
                        "agent_url": agent_url,
                    },
                )

            if response.status_code >= 400:
                raise AgentResponseError(
                    message=f"Agent returned error: {response.status_code}",
                    error_code="AGENT_ERROR",
                    context={
                        "status_code": response.status_code,
                        "response": response.text[:200],
                    },
                )

            result = response.json()

            # Validate response structure
            if not isinstance(result, dict) or "response" not in result:
                raise AgentResponseError(
                    message="Invalid response format from agent",
                    error_code="INVALID_RESPONSE",
                    context={"response": str(result)[:200]},
                )

            logger.info(
                f"Successfully dispatched to {agent_url}",
                extra={"agent_url": agent_url},
            )

            return result

    except httpx.TimeoutException as e:
        raise AgentTimeoutError(
            message=f"Agent timeout after {timeout}s",
            error_code="AGENT_TIMEOUT",
            context={"agent_url": agent_url, "timeout": timeout},
            cause=e,
        ) from e


# Example 6: Retry with custom callback
def on_retry_callback(error: Exception, attempt: int):
    """Custom callback called before each retry."""
    logger.warning(
        f"Retry attempt {attempt} after error: {error}",
        extra={"error_type": type(error).__name__},
    )
    # Could send metric, notification, etc.


@with_retry(
    max_attempts=3, backoff=BackoffStrategy.EXPONENTIAL, on_retry=on_retry_callback
)
async def operation_with_retry_callback():
    """Operation with custom retry callback for monitoring."""
    # Your operation here
    return {"status": "success"}


# Example 7: Multiple circuit breakers for different services
async def orchestrate_multi_service_operation(meeting_id: str) -> Dict[str, Any]:
    """Orchestrate operation across multiple services.

    Each service has its own circuit breaker for independent failure handling.
    """
    # Each call protected by its own circuit breaker
    docs = await call_google_docs_api("documents.get", documentId=meeting_id)
    tickets = await call_jira_api(f"search?jql=meeting={meeting_id}")

    return {"documents": docs, "tickets": tickets}


def format_query(action_item: Dict[str, Any]) -> str:
    """Format action item as query for agent."""
    return (
        f"Create {action_item.get('category', 'task')}: "
        f"{action_item.get('title')} - {action_item.get('description')}"
    )


# Example 8: Monitoring circuit breaker state
def monitor_circuit_breakers():
    """Monitor and log circuit breaker states."""
    breakers = get_all_circuit_breakers()

    for name, breaker in breakers.items():
        stats = breaker.get_stats()
        logger.info(f"Circuit breaker '{name}' status", extra=stats)

        # Alert if circuit is open
        if stats["state"] == "open":
            logger.error(f"⚠️  Circuit breaker '{name}' is OPEN!", extra=stats)


# Example usage in main workflow
async def example_workflow():
    """Example workflow using error handling components."""

    # 1. Fetch document with retry
    try:
        doc = await fetch_document("doc-123")
        logger.info(f"Fetched document: {doc.get('title')}")
    except Exception as e:
        logger.error(f"Failed to fetch document: {e}")
        return

    # 2. Process with error context
    action_items = [
        {"title": "Fix bug", "description": "Fix login bug", "category": "jira"},
        {
            "title": "Update docs",
            "description": "Update API docs",
            "category": "google",
        },
    ]

    results = []
    for item in action_items:
        try:
            async with ErrorContext("dispatch_action_item", title=item["title"]):
                result = await dispatch_to_agent(item, "http://jira-agent:8000")
                results.append(result)
        except Exception as e:
            logger.error(f"Failed to dispatch {item['title']}: {e}")
            results.append({"error": str(e)})

    # 3. Monitor circuit breakers
    monitor_circuit_breakers()

    return results


if __name__ == "__main__":
    # Run example workflow
    asyncio.run(example_workflow())
