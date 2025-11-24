"""Agent Dispatch Workflow.

This workflow handles dispatching action items to agents using pre-determined
routing decisions and collecting results.
"""

from urllib.parse import urljoin

import httpx
from llama_index.core.workflow import Context, Event, StartEvent, Workflow, step
from pydantic import HttpUrl

from src.core.error_handler import (
    AgentResponseError,
    AgentTimeoutError,
    AgentUnavailableError,
    BackoffStrategy,
    ErrorContext,
    with_circuit_breaker,
    with_retry,
)
from src.core.schemas.workflow_models import (
    ActionItem,
    ActionItemsList,
    AgentExecutionResult,
)
from src.core.workflows.common_events import StopWithErrorEvent
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import AGENT_QUERY_PROMPT
from src.services.registry.registry_client import get_registry_client

logger = get_logger("workflows.agent_dispatch")


class ActionItemsInput(Event):
    """Input event containing action items to dispatch."""

    action_items: ActionItemsList


class ExecutionRequired(Event):
    """Event indicating agent execution is needed."""

    action_item_index: int
    action_item: ActionItem
    agent_url: HttpUrl | None


class ExecutionCompleted(Event):
    """Event indicating agent execution has completed."""

    result: AgentExecutionResult


class AgentDispatchWorkflow(Workflow):
    """Workflow for routing action items to appropriate agents and executing them.

    This workflow uses the agent registry for dynamic agent discovery and
    LLMTextCompletionProgram for structured routing decisions.
    """

    def __init__(self, llm, *args, **kwargs):
        """Initialize the workflow.

        Args:
            llm: Language model for routing decisions
        """
        super().__init__(*args, **kwargs)
        self.llm = llm
        logger.info("Initialized AgentDispatchWorkflow")

    @step
    async def initialize_dispatch(self, event: StartEvent) -> ActionItemsInput:
        """Initialize dispatch workflow with action items from StartEvent."""
        logger.info("Initializing agent dispatch workflow")

        # Extract action items from StartEvent
        action_items = event.action_items
        logger.info(
            f"Received {len(action_items.action_items)} action items for dispatch"
        )
        return ActionItemsInput(action_items=action_items)

    @step(pass_context=True)
    async def route_action_items(
        self, ctx: Context, event: ActionItemsInput
    ) -> ExecutionRequired | StopWithErrorEvent | None:
        """Dispatch action items using pre-determined routing decisions.

        This step uses the routing information already embedded in each
        action item (assigned_agent and routing_reason fields) rather than
        making new routing decisions.
        """
        logger.info(f"Dispatching {len(event.action_items.action_items)} action items")

        # Discover available agents to get their endpoints
        try:
            registry_client = get_registry_client()
            available_agents = await registry_client.discover_agents()

            if not available_agents:
                logger.warning("No agents found in registry")
                return StopWithErrorEvent(result="no_agents_available", error=True)

            logger.info(f"Found {len(available_agents)} available agents")

        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return StopWithErrorEvent(result="agent_discovery_error", error=True)

        # Process action items using pre-existing routing decisions
        try:
            # Store total count for result collection
            await ctx.store.set(
                "total_executions", len(event.action_items.action_items)
            )

            # Process each action item using its pre-determined routing
            for idx, action_item in enumerate(event.action_items.action_items):
                try:
                    # Use the routing decision already in the action item
                    assigned_agent = action_item.assigned_agent or "UNASSIGNED_AGENT"

                    logger.debug(
                        f"Dispatching action item {idx}: {action_item.title} "
                        f"to {assigned_agent}"
                    )

                    # Find the agent endpoint
                    agent_url = None
                    if assigned_agent != "UNASSIGNED_AGENT":
                        logger.debug(
                            f"Looking for agent '{assigned_agent}' in registry. "
                            f"Available agents: "
                            f"{[a.agent_id for a in available_agents]}"
                        )
                        selected_agent = self._find_agent_by_id(
                            available_agents, assigned_agent
                        )
                        if selected_agent:
                            agent_url = selected_agent.endpoint
                            logger.info(
                                f"Dispatching '{action_item.title}' to "
                                f"{selected_agent.name} at {agent_url}"
                            )
                        else:
                            logger.warning(
                                f"Agent '{assigned_agent}' not found in registry, "
                                "marking as unassigned. "
                                f"Available agents: "
                                f"{[a.agent_id for a in available_agents]}"
                            )
                            # Update action item to reflect unavailable agent
                            action_item.assigned_agent = "UNASSIGNED_AGENT"
                            action_item.routing_reason = (
                                f"Agent '{assigned_agent}' no longer available"
                            )

                    # Dispatch execution for this action item
                    ctx.send_event(
                        ExecutionRequired(
                            action_item_index=idx,
                            action_item=action_item,
                            agent_url=agent_url,
                        )
                    )

                    logger.debug(f"Dispatched execution for action item {idx}")

                except Exception as e:
                    logger.error(f"Error dispatching action item {idx}: {e}")
                    # Update action item to mark dispatch failure
                    action_item.assigned_agent = "UNASSIGNED_AGENT"
                    action_item.routing_reason = f"Error during dispatch: {str(e)}"
                    # Send execution for failed dispatch
                    ctx.send_event(
                        ExecutionRequired(
                            action_item_index=idx,
                            action_item=action_item,
                            agent_url=None,
                        )
                    )

            logger.info(
                f"Completed dispatch for {len(event.action_items.action_items)} "
                "action items"
            )

            # Return None since we've dispatched executions
            return None

        except Exception as e:
            logger.error(f"Error during dispatch process: {e}")
            return StopWithErrorEvent(result="dispatch_error", error=True)

    @with_retry(
        max_attempts=3,
        backoff=BackoffStrategy.EXPONENTIAL_JITTER,
        base_delay=2.0,
        max_delay=30.0,
        retryable_exceptions=(
            httpx.TimeoutException,
            httpx.NetworkError,
            AgentTimeoutError,
            AgentUnavailableError,
        ),
    )
    @with_circuit_breaker(
        name="agent_dispatch", failure_threshold=5, recovery_timeout=60.0
    )
    async def _call_agent_with_resilience(
        self, agent_url: str, query: str, agent_name: str
    ) -> dict:
        """Call agent with retry and circuit breaker protection.

        Args:
            agent_url: Agent endpoint URL
            query: Formatted query for agent
            agent_name: Name of agent for logging

        Returns:
            Agent response data

        Raises:
            AgentTimeoutError: If agent times out
            AgentUnavailableError: If agent returns 5xx error
            AgentResponseError: If agent returns 4xx error or invalid response
        """
        async with ErrorContext(
            "call_agent", agent_name=agent_name, agent_url=agent_url
        ):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(agent_url, json={"query": query})

                    # Handle 5xx errors (service unavailable)
                    if response.status_code >= 500:
                        raise AgentUnavailableError(
                            message=f"Agent {agent_name} unavailable",
                            error_code="AGENT_UNAVAILABLE",
                            context={
                                "agent_name": agent_name,
                                "agent_url": agent_url,
                                "status_code": response.status_code,
                            },
                        )

                    # Handle 4xx errors (client errors)
                    if response.status_code >= 400:
                        raise AgentResponseError(
                            message=f"Agent {agent_name} error",
                            error_code="AGENT_ERROR",
                            context={
                                "agent_name": agent_name,
                                "status_code": response.status_code,
                                "response": response.text[:200],
                            },
                        )

                    response_data = response.json()

                    # Validate response structure
                    if not isinstance(response_data, dict):
                        raise AgentResponseError(
                            message="Invalid response format from agent",
                            error_code="INVALID_RESPONSE",
                            context={
                                "agent_name": agent_name,
                                "response": str(response_data)[:200],
                            },
                        )

                    logger.info(f"Agent {agent_name} completed execution")
                    return response_data

            except httpx.TimeoutException as e:
                raise AgentTimeoutError(
                    message=f"Agent {agent_name} timeout after 120s",
                    error_code="AGENT_TIMEOUT",
                    context={
                        "agent_name": agent_name,
                        "agent_url": agent_url,
                        "timeout": 120.0,
                    },
                    cause=e,
                ) from e

    @step
    async def execute_single_action(
        self, event: ExecutionRequired
    ) -> ExecutionCompleted:
        """Execute a single action item via the assigned agent."""

        action_item = event.action_item
        assigned_agent = action_item.assigned_agent or "UNASSIGNED_AGENT"

        logger.info(f"Executing action item via {assigned_agent}")

        if assigned_agent == "UNASSIGNED_AGENT":
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=event.action_item_index,
                    action_item=action_item,
                    agent_name=assigned_agent,
                    request_error=True,
                    agent_error=True,
                    response=(
                        "No suitable agent found for this action item. "
                        "Agent routing failed."
                    ),
                )
            )

        try:
            # Use the provided agent URL
            logger.debug(f"Agent URL for {assigned_agent}: {event.agent_url}")
            if not event.agent_url:
                logger.error(
                    f"No URL provided for agent: {assigned_agent}. "
                    f"Event data: action_item_index={event.action_item_index}, "
                    f"agent_url={event.agent_url}"
                )
                return ExecutionCompleted(
                    result=AgentExecutionResult(
                        action_item_index=event.action_item_index,
                        action_item=action_item,
                        agent_name=assigned_agent,
                        request_error=True,
                        agent_error=True,
                        response=(
                            f"Agent URL not provided. No URL for agent "
                            f"{assigned_agent}"
                        ),
                    )
                )

            # Execute via agent API
            # Use urljoin to properly combine URL parts
            agent_url = urljoin(str(event.agent_url), "/agent")

            # Format the query with individual fields from the action item
            query = AGENT_QUERY_PROMPT.format(
                title=getattr(action_item, "title", "N/A"),
                description=getattr(action_item, "description", "N/A"),
                assignee=getattr(action_item, "assignee", "TBD"),
                due_date=str(getattr(action_item, "due_date", "TBD")),
                priority=getattr(action_item, "priority", "medium"),
                category=getattr(action_item, "category", "general"),
            )

            # Call agent with retry and circuit breaker protection
            response_data = await self._call_agent_with_resilience(
                agent_url=agent_url, query=query, agent_name=assigned_agent
            )

            logger.debug(f"response data: {response_data}")

            # Extract fields from agent response
            agent_response_content = response_data.get("response", str(response_data))
            agent_error = response_data.get("error", False)
            additional_info_required = response_data.get(
                "additional_info_required", False
            )

            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=event.action_item_index,
                    action_item=action_item,
                    agent_name=assigned_agent,
                    request_error=False,
                    agent_error=agent_error,
                    response=agent_response_content,
                    additional_info_required=additional_info_required,
                )
            )

        except (AgentTimeoutError, AgentUnavailableError, AgentResponseError) as e:
            logger.error(f"Agent error for {assigned_agent}: {e.message}")
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=event.action_item_index,
                    action_item=action_item,
                    agent_name=assigned_agent,
                    request_error=True,
                    agent_error=True,
                    response=f"Agent execution failed: {e.message}",
                )
            )
        except Exception as e:
            logger.error(f"Unexpected error executing action item: {e}")
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=event.action_item_index,
                    action_item=action_item,
                    agent_name=assigned_agent,
                    request_error=True,
                    agent_error=True,
                    response=f"Unexpected execution error: {str(e)}",
                )
            )

    @step
    async def collect_execution_results(
        self, ctx: Context, event: ExecutionCompleted
    ) -> StopWithErrorEvent | None:
        """Collect results from all agent executions."""

        total_executions = await ctx.store.get("total_executions")
        results = ctx.collect_events(event, [ExecutionCompleted] * total_executions)

        if results is None:
            return None

        logger.info(f"Collected {len(results)} execution results")

        # Extract results and compile summary
        execution_results = [result.result for result in results]
        successful_executions = sum(
            1
            for result in execution_results
            if not result.request_error and not result.agent_error
        )

        logger.info(
            f"Execution summary: {successful_executions}/"
            f"{len(execution_results)} successful"
        )

        return StopWithErrorEvent(result=execution_results, error=False)

    def _find_agent_by_id(self, agents, agent_id: str):
        """Find agent by ID from the available agents list."""
        # Try exact match by agent_id first
        for agent in agents:
            if agent.agent_id == agent_id:
                return agent

        return None
