"""Agent Dispatch Workflow.

This workflow handles routing action items to appropriate agents and collecting results.
"""

import requests
from llama_index.core.program import LLMTextCompletionProgram
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    Workflow,
    step,
)
from pydantic import HttpUrl

from src.core.workflows.common_events import StopWithErrorEvent
from src.core.workflows.models import (
    ActionItemsList,
    AgentExecutionResult,
    AgentRoutingDecision,
)
from src.infrastructure.logging.logging_config import get_logger
from src.infrastructure.prompts.prompts import (
    AGENT_QUERY_PROMPT,
    TOOL_DISPATCHER_PROMPT,
)
from src.infrastructure.registry.registry_client import get_registry_client

logger = get_logger("workflows.agent_dispatch")


class ActionItemsInput(Event):
    """Input event containing action items to dispatch."""

    action_items: ActionItemsList


class ExecutionRequired(Event):
    """Event indicating agent execution is needed."""

    decision: AgentRoutingDecision
    action_item_data: dict
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
        """Route action items to appropriate agents and dispatch execution immediately.

        This combined approach improves performance by dispatching executions
        as soon as each routing decision is made, rather than waiting for
        all routing decisions to complete.

        Uses agent registry to discover available agents and LLM to
        make routing decisions.
        """
        logger.info(f"Routing {len(event.action_items.action_items)} action items")

        # Discover available agents
        try:
            registry_client = get_registry_client()
            available_agents = await registry_client.discover_agents()

            if not available_agents:
                logger.warning("No agents found in registry")
                return StopWithErrorEvent(result="no_agents_available", error=True)

            logger.info(f"Found {len(available_agents)} available agents")

            # Build agent descriptions for LLM decision making
            agent_descriptions = []
            for agent in available_agents:
                agent_descriptions.append(f"{agent.name}: {agent.description}")

        except Exception as e:
            logger.error(f"Failed to discover agents: {e}")
            return StopWithErrorEvent(result="agent_discovery_error", error=True)

        # Create structured program for routing decisions
        try:
            routing_program = LLMTextCompletionProgram.from_defaults(
                llm=self.llm,
                output_cls=AgentRoutingDecision,
                prompt=TOOL_DISPATCHER_PROMPT,
                verbose=True,
            )

            # Store total count for result collection
            await ctx.store.set(
                "total_executions", len(event.action_items.action_items)
            )

            # Process each action item: route and immediately dispatch execution
            for idx, action_item in enumerate(event.action_items.action_items):
                try:
                    logger.debug(f"Routing action item {idx}: {action_item.title}")

                    # Get structured routing decision
                    decision = await routing_program.acall(
                        action_item=action_item.model_dump(),
                        agents_list="\\n".join(agent_descriptions),
                        action_item_index=idx,
                    )

                    # Find the selected agent by name
                    selected_agent = self._find_agent_by_name(
                        available_agents, decision.agent_name
                    )

                    agent_url = None
                    if selected_agent:
                        decision.agent_name = selected_agent.agent_id
                        agent_url = selected_agent.endpoint
                        logger.info(
                            f"Routed '{action_item.title}' to {selected_agent.name}"
                        )
                    else:
                        logger.warning(
                            f"Agent '{decision.agent_name}' not "
                            "found, marking as unassigned"
                        )
                        decision.agent_name = "UNASSIGNED_AGENT"

                    # Immediately dispatch execution for this action item
                    ctx.send_event(
                        ExecutionRequired(
                            decision=decision,
                            action_item_data=action_item.model_dump(),
                            agent_url=agent_url,
                        )
                    )

                    logger.debug(f"Dispatched execution for action item {idx}")

                except Exception as e:
                    logger.error(f"Error routing action item {idx}: {e}")
                    # Send unassigned execution for failed routing
                    unassigned_decision = AgentRoutingDecision(
                        action_item_index=idx,
                        agent_name="UNASSIGNED_AGENT",
                        routing_reason=f"Error during routing: {str(e)}",
                        requires_human_approval=True,
                    )
                    ctx.send_event(
                        ExecutionRequired(
                            decision=unassigned_decision,
                            action_item_data=action_item.model_dump(),
                            agent_url=None,
                        )
                    )

            logger.info(
                "Completed routing and dispatch for "
                f"{len(event.action_items.action_items)} action items"
            )

            # Return None since we've dispatched executions and don't
            # need to return routing decisions
            return None

        except Exception as e:
            logger.error(f"Error during routing process: {e}")
            return StopWithErrorEvent(result="routing_error", error=True)

    @step
    async def execute_single_action(
        self, event: ExecutionRequired
    ) -> ExecutionCompleted:
        """Execute a single action item via the assigned agent."""

        action_item = event.action_item_data
        decision = event.decision

        logger.info(f"Executing action item via {decision.agent_name}")

        if decision.agent_name == "UNASSIGNED_AGENT":
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=decision.action_item_index,
                    agent_name=decision.agent_name,
                    success=False,
                    result="No suitable agent found for this action item",
                    error_message="Agent routing failed",
                )
            )

        try:
            # Use the provided agent URL
            if not event.agent_url:
                logger.error(f"No URL provided for agent: {decision.agent_name}")
                return ExecutionCompleted(
                    result=AgentExecutionResult(
                        action_item_index=decision.action_item_index,
                        agent_name=decision.agent_name,
                        success=False,
                        result="Agent URL not provided",
                        error_message=(
                            "No URL provided for agent " f"{decision.agent_name}"
                        ),
                    )
                )

            # Execute via agent API
            agent_url = f"{event.agent_url}/agent"

            response = requests.post(
                agent_url,
                json={"query": AGENT_QUERY_PROMPT.format(action_item=action_item)},
                timeout=120,
            )
            response.raise_for_status()

            response_data = response.json()
            logger.info(f"Agent {decision.agent_name} completed execution")

            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=decision.action_item_index,
                    agent_name=decision.agent_name,
                    success=True,
                    result=str(response_data),
                    error_message=None,
                )
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling agent {decision.agent_name}: {e}")
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=decision.action_item_index,
                    agent_name=decision.agent_name,
                    success=False,
                    result="Agent execution failed",
                    error_message=str(e),
                )
            )
        except Exception as e:
            logger.error(f"Unexpected error executing action item: {e}")
            return ExecutionCompleted(
                result=AgentExecutionResult(
                    action_item_index=decision.action_item_index,
                    agent_name=decision.agent_name,
                    success=False,
                    result="Unexpected execution error",
                    error_message=str(e),
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
        successful_executions = sum(1 for result in execution_results if result.success)

        logger.info(
            f"Execution summary: {successful_executions}/"
            f"{len(execution_results)} successful"
        )

        return StopWithErrorEvent(result=execution_results, error=False)

    def _find_agent_by_name(self, agents, agent_name: str):
        """Find agent by name from the available agents list."""
        agent_name = agent_name.lower().strip()

        # Try exact match by name first
        for agent in agents:
            if agent.name.lower() == agent_name:
                return agent

        # Try partial match by name
        for agent in agents:
            if agent_name in agent.name.lower() or agent.name.lower() in agent_name:
                return agent

        return None
