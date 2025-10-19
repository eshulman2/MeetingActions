"""Action Items Dispatch Orchestrator.

This workflow orchestrates the dispatch of action items to appropriate agents.
It uses the AgentDispatchWorkflow to route and execute action items.
"""

from typing import Any

from llama_index.core.workflow import (
    StartEvent,
    Workflow,
    step,
)

from src.core.schemas.workflow_models import ActionItemsList, AgentExecutionResult
from src.core.workflows.common_events import StopWithErrorEvent
from src.core.workflows.sub_workflows.agent_dispatch_workflow import (
    AgentDispatchWorkflow,
)
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("workflows.action_items_dispatch")


class ActionItemsDispatchOrchestrator(Workflow):
    """Orchestrator workflow for dispatching action items to agents.

    This workflow provides:
    1. Agent routing and execution via AgentDispatchWorkflow
    2. Centralized error handling and logging
    3. Result compilation and reporting
    """

    def __init__(
        self,
        llm,
        *args: Any,
        **kwargs: Any,
    ):
        """Initialize the orchestrator workflow.

        Args:
            llm: Language model for routing decisions and instruction generation
        """
        super().__init__(*args, **kwargs)
        self.llm = llm

        logger.info("Initialized ActionItemsDispatchOrchestrator")

    @step
    async def dispatch_to_agents(self, event: StartEvent) -> StopWithErrorEvent:
        """Dispatch action items to agents using the AgentDispatchWorkflow.

        Args:
            event: StartEvent with 'action_items' parameter (ActionItemsList)

        Returns:
            StopWithErrorEvent with execution results or error
        """
        action_items = event.action_items

        # Validate input
        if not isinstance(action_items, ActionItemsList):
            logger.error("Input action_items is not of type ActionItemsList")
            return StopWithErrorEvent(result="invalid_input", error=True)

        logger.info(
            f"Dispatching {len(action_items.action_items)} action items to agents"
        )

        try:
            # Initialize and run the agent dispatch workflow
            dispatch_workflow = AgentDispatchWorkflow(llm=self.llm, timeout=120)

            dispatch_result = await dispatch_workflow.run(action_items=action_items)

            # Handle results
            if hasattr(dispatch_result, "error") and dispatch_result.error:
                logger.error(f"Agent dispatch failed: {dispatch_result.result}")
                return StopWithErrorEvent(result=dispatch_result.result, error=True)

            # Extract execution results
            execution_results = (
                dispatch_result.result
                if hasattr(dispatch_result, "result")
                else dispatch_result
            )

            # Compile final summary
            if isinstance(execution_results, list):
                successful_count = sum(
                    1
                    for result in execution_results
                    if isinstance(result, AgentExecutionResult)
                    and not result.request_error
                    and not result.agent_error
                )

                logger.info(
                    f"Action items dispatch completed: "
                    f"{successful_count}/{len(execution_results)} successful executions"
                )

            return StopWithErrorEvent(result=execution_results, error=False)

        except Exception as e:
            logger.error(f"Error dispatching to agents: {e}")
            return StopWithErrorEvent(result="dispatch_error", error=True)
