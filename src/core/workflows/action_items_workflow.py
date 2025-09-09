"""Action Items Workflow for Meeting Notes Processing.

This module implements a comprehensive workflow for processing meeting notes
and generating structured action items. The workflow includes multiple steps
for content analysis, validation, review cycles, and integration with external
agent systems for task execution.

The workflow uses LlamaIndex's event-driven architecture to handle complex
multi-step processes with error handling, retry mechanisms, and observability.
"""

import json
import re
from typing import Any, Dict
from urllib.parse import urlencode

import nest_asyncio
import requests
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.memory import Memory
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)

from src.infrastructure.config import (
    ACTION_ITEMS_CONTEXT,
    ACTION_ITEMS_PROMPT,
    AGENT_QUERY_PROMPT,
    JSON_REFLECTION_PROMPT,
    REFLECTION_PROMPT,
    REVIEW_CONTEXT,
    REVIEWER_PROMPT,
    TOOL_DISPATCHER_CONTEXT,
    TOOL_DISPATCHER_PROMPT,
    get_config,
)
from src.infrastructure.logging.logging_config import get_logger

logger = get_logger("workflows.action_items_workflow")
config = get_config()

nest_asyncio.apply()


class MeetingNotesEvent(Event):
    """Event containing meeting notes content for processing.

    Attributes:
        meeting_notes: The raw meeting notes text content
    """

    meeting_notes: str


class ReviewErrorEvent(Event):
    """Event triggered when review identifies errors in action items.

    Attributes:
        review: The review feedback indicating what needs to be changed
        action_items: The action items that were reviewed and found to have errors
    """

    review: str
    action_items: str


class ActionItemsDone(Event):
    """Event triggered when action items have been created or updated.

    Attributes:
        action_items: The generated action items content
    """

    meeting_notes: str
    action_items: str


class JsonCheckEvent(Event):
    """Event triggered to validate JSON format of action items.

    Attributes:
        action_items: The action items to be validated for JSON format
    """

    action_items: str


class JsonCheckError(Event):
    """Event triggered when JSON validation fails.

    Attributes:
        wrong_answer: The malformed response that failed JSON validation
        error: The specific error encountered during JSON parsing
    """

    wrong_answer: str
    error: Any


class ToolRouter(Event):
    """Event for routing action items to appropriate agent tools.

    Attributes:
        action_items: Dictionary containing structured action items
    """

    action_items: Dict


class DispatchToAgent(Event):
    """Event for dispatching individual action items to specific agents.

    Attributes:
        agent: Name/identifier of the target agent
        action_item: Single action item dictionary to be processed
    """

    agent: str
    action_item: Dict


class NoActionCall(Event):
    """Event triggered when no agent action is required for an action item.

    Attributes:
        action_item: Action item that doesn't require agent processing
    """

    action_item: Dict


class ToolResult(Event):
    """Event containing the result of agent tool execution.

    Attributes:
        action_item: The action item that was processed
        response: Response from the agent tool execution
        error: Boolean indicating if an error occurred during execution
    """

    action_item: Dict
    response: str
    error: bool


class ActionItemsWorkflow(Workflow):
    """Workflow for processing meeting notes and generating action items.

    This workflow takes meeting notes as input and generates structured action items
    through a multi-step process including creation, review, and JSON validation.
    """

    def __init__(
        self,
        llm,
        *args: Any,
        max_iterations: int,  # Pass custom parameters too.
        **kwargs: Any,
    ) -> None:
        """Initialize the WorkItemWorkflow.

        Args:
            max_iterations: Maximum number of retry iterations for
                action item generation
            *args: Additional positional arguments passed to parent Workflow
            **kwargs: Additional keyword arguments passed to parent Workflow
        """
        logger.info(
            "Initializing ActionItemsWorkflow with max_iterations: " f"{max_iterations}"
        )

        # Initialize the super class
        super().__init__(*args, **kwargs)
        # Store input into instance variables
        self.max_retries = max_iterations
        self.memory = Memory.from_defaults(session_id="my_session", token_limit=40000)
        self.llm = llm
        logger.debug("ActionItemsWorkflow initialized successfully")

    @step
    async def get_meeting_notes(
        self, event: StartEvent
    ) -> MeetingNotesEvent | StopEvent:
        """Retrieve meeting notes from the configured endpoint.

        This step fetches meeting notes from an external API endpoint based
        on the meeting name and date provided in the StartEvent.

        Args:
            ctx: Workflow context for state management
            event: StartEvent containing meeting and date parameters

        Returns:
            MeetingNotesEvent with the retrieved notes, or StopEvent if error

        Raises:
            requests.exceptions.RequestException: If API request fails
        """
        logger.info(
            f"Getting meeting notes for meeting: {event['meeting']}, "
            f"date: {event['date']}"
        )
        encoded_url = urlencode({"meeting": event["meeting"], "date": event["date"]})
        try:
            response = requests.get(
                f"{config.config.meeting_notes_endpoint}?{encoded_url}",
                timeout=30,
            )
            response.raise_for_status()
            logger.debug("Successfully retrieved meeting notes from API")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while fetching meeting notes: {e}")
            raise requests.exceptions.RequestException from e

        response_json = response.json()
        logger.info("Meeting notes retrieved and parsed successfully")
        logger.debug(f"Received the following meeting notes:\n{response_json}")

        if response_json["error"]:
            return StopEvent("oh no an error occurred")

        return MeetingNotesEvent(meeting_notes=response_json["response"])

    @step
    async def create_action_items(
        self,
        ctx: Context,
        event: MeetingNotesEvent | ReviewErrorEvent | JsonCheckError,
    ) -> StopEvent | ActionItemsDone:
        """Create or refine action items based on meeting notes and feedback.

        Args:
            ctx: Workflow context for storing state
            event: The triggering event (start, review error, or JSON error)

        Returns:
            StopEvent if max retries reached or no input provided,
            ActionItemsDone if action items were successfully created
        """
        current_retries = await ctx.store.get("retries", default=0)
        logger.debug(
            "Creating action items, attempt "
            f"{current_retries + 1}/{self.max_retries}"
        )

        if current_retries >= self.max_retries:
            logger.warning("Max retries reached for action items creation")
            return StopEvent(result="Max retries reached", error=True)
        await ctx.store.set("retries", current_retries + 1)

        if isinstance(event, MeetingNotesEvent):
            if not event.meeting_notes:
                logger.error("No meeting notes provided as input")
                return StopEvent(result="no input was provided", error=True)
            logger.info("Starting action items creation from meeting notes")

            self.memory.put_messages(
                [
                    ChatMessage(role=MessageRole.SYSTEM, content=ACTION_ITEMS_CONTEXT),
                    ChatMessage(
                        role=MessageRole.USER,
                        content=ACTION_ITEMS_PROMPT.format(
                            meeting_notes=event.meeting_notes
                        ),
                    ),
                ]
            )

        elif isinstance(event, ReviewErrorEvent):
            logger.info("Refining action items based on review feedback")
            review = event.review
            action_items = event.action_items
            self.memory.put(
                ChatMessage(
                    role=MessageRole.USER,
                    content=REFLECTION_PROMPT.format(
                        review=review, action_items=action_items
                    ),
                )
            )

        elif isinstance(event, JsonCheckError):
            logger.info("Fixing JSON formatting issues in action items")
            output = await self.llm.achat(
                [
                    ChatMessage(
                        role=MessageRole.USER,
                        content=JSON_REFLECTION_PROMPT.format(
                            wrong_answer=event.wrong_answer, error=event.error
                        ),
                    )
                ]
            )
            logger.debug("JSON formatting fix applied")
            print(output)
            return JsonCheckEvent(action_items=str(output))

        output = await self.llm.achat(self.memory.get())
        logger.debug("LLM response generated for action items")

        self.memory.put(ChatMessage(role=MessageRole.ASSISTANT, content=output))

        logger.info("Action items created successfully")
        return ActionItemsDone(
            action_items=str(output), meeting_notes=event.meeting_notes
        )

    @step
    async def review(
        self,
        event: ActionItemsDone,
    ) -> JsonCheckEvent | ReviewErrorEvent:
        """Review generated action items for quality and accuracy.

        Args:
            event: ActionItemsDone event containing the action items to review

        Returns:
            JsonCheckEvent if no changes required,
            ReviewErrorEvent if improvements are needed
        """
        logger.info("Reviewing generated action items for quality")
        review = await self.llm.achat(
            [
                ChatMessage(role=MessageRole.SYSTEM, content=REVIEW_CONTEXT),
                ChatMessage(
                    role=MessageRole.USER,
                    content=REVIEWER_PROMPT.format(
                        action_items=event.action_items,
                        meeting_notes=event.meeting_notes,
                    ),
                ),
            ]
        )
        if "No Changes Required" in str(review):
            logger.info("Review passed: No changes required")
            return JsonCheckEvent(action_items=event.action_items)
        logger.info("Review identified issues: Changes required")
        return ReviewErrorEvent(action_items=event.action_items, review=str(review))

    @step
    async def json_check(self, event: JsonCheckEvent) -> ToolRouter | JsonCheckError:
        """Validate that action items are in proper JSON format.

        Args:
            event: JsonCheckEvent containing action items to validate

        Returns:
            StopEvent with the valid JSON if successful,
            JsonCheckError if JSON parsing fails
        """
        logger.info("Validating action items JSON format")
        try:
            match = re.search(r"\{.*\}", event.action_items, re.DOTALL)
            if not match:
                logger.warning("No JSON found in action items output")
                return JsonCheckError(
                    wrong_answer=event.action_items,
                    error="no Json was found in the output",
                )
            j = json.loads(match.group(0))
            logger.info("JSON validation successful")
            return ToolRouter(action_items=j)
        except json.JSONDecodeError as err:
            logger.error(f"JSON validation failed: {err}")
            return JsonCheckError(wrong_answer=event.action_items, error=err)

    @step
    async def tool_router(
        self, ctx: Context, event: ToolRouter
    ) -> DispatchToAgent | None:
        """Route action items to appropriate agents based on their capabilities.

        This step analyzes each action item and determines which agent is best
        suited to handle it based on agent descriptions and capabilities.

        Args:
            ctx: Workflow context for state management
            event: ToolRouter event containing action items to route

        Returns:
            DispatchToAgent events for each routable action item, or None
        """
        agent_list = []
        for agent, url in config.config.agents.items():
            try:
                logger.debug(f"Fetching {agent} agent description")
                res = requests.get(f"{url}/description", timeout=5)
                res.raise_for_status()
                agent_list.append(f"{agent}: {res.content.decode('utf-8')}")
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Unable to load {agent} agent description "
                    f"with the following exception: {e}"
                )

        tool_calls = 0
        for action_item in event.action_items["action_items"]:
            try:
                res = await self.llm.achat(
                    [
                        ChatMessage(
                            role=MessageRole.SYSTEM,
                            content=TOOL_DISPATCHER_CONTEXT,
                        ),
                        ChatMessage(
                            role=MessageRole.USER,
                            content=TOOL_DISPATCHER_PROMPT.format(
                                action_item=action_item,
                                agents_list="\n".join(agent_list),
                            ),
                        ),
                    ]
                )
                logger.info(
                    "Dispatching action item: "
                    f"{action_item["description"]} "
                    f"to agent {str(res)}"
                )
                ctx.send_event(DispatchToAgent(agent=str(res), action_item=action_item))
                tool_calls += 1
            except Exception as e:
                logger.error(e)

        ctx.store.set("tool_calls", tool_calls)
        return None

    @step
    async def dispatch_to_agent(self, event: DispatchToAgent) -> ToolResult:
        """Dispatch action item to the specified agent for execution.

        This step sends an action item to the designated agent and processes
        the response, handling both successful executions and errors.

        Args:
            ctx: Workflow context for state management
            event: DispatchToAgent event with agent and action item details

        Returns:
            ToolResult containing the agent's response and execution status
        """
        if event.agent == "UNASSIGNED_AGENT":
            return ToolResult(
                action_item=event.action_item["description"],
                response="No suitable agent found to preform this action item",
                error=False,
            )
        try:
            res = requests.post(
                f"{config.config.agents}/agent",
                json={"query": AGENT_QUERY_PROMPT.format(event.action_item)},
                timeout=30,
            )
            logger.debug(res.json())
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while calling {event.agent} agent: {e}")
            return ToolResult(
                action_item=event.action_item["description"],
                response=f"An error occurred while calling {event.agent} agent: {e}",
                error=True,
            )

        return ToolResult(
            action_item=event.action_item["description"],
            response=res.json(),
            error=False,
        )

    @step
    async def collect_tool_results(
        self, ctx: Context, event: ToolResult
    ) -> StopEvent | None:
        """Collect and aggregate results from all agent tool executions.

        This step waits for all dispatched action items to complete and
        aggregates their results for final workflow output.

        Args:
            ctx: Workflow context for state management
            event: ToolResult from individual agent execution

        Returns:
            StopEvent with aggregated results when all tools complete,
            or None if still waiting for more results
        """
        tool_calls = ctx.store.get("tool_calls")
        result = ctx.collect_events(event, [ToolResult] * tool_calls)
        if result is None:
            return None

        print(result)
        return StopEvent(result="Done")
