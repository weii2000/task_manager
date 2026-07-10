from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from agent.prompt import AgentPromptBuilder
from agent.provider import LLMProvider
from agent.state import (
    Action,
    AgentPhase,
    AvailableTool,
    BaseDecision,
    Message,
    MessageRole,
    PlanDecision,
    ReviewDecision,
    State,
    ToolError,
    ToolResult,
    ToolResultStatus,
)
from agent.tools.base import ToolContext
from agent.tools.registry import get_tool_definition
from exceptions.agent import AgentResponseFormatError
from exceptions.base import AppError


DecisionT = TypeVar("DecisionT", bound=BaseDecision)


class Node:
    def __init__(self) -> None:
        self.successors: dict[str, Node] = {}
        self._action = "default"

    async def exec(self, state: State, context: ToolContext) -> State:
        raise NotImplementedError

    def __rshift__(self, other: "Node") -> "Node":
        self.successors[self._action] = other
        self._action = "default"
        return other

    def __sub__(self, action: str) -> "Node":
        self._action = action or "default"
        return self


class LLMDecisionNode(Node, Generic[DecisionT], ABC):
    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: AgentPromptBuilder,
        response_model: type[DecisionT],
        allowed_tools: frozenset[AvailableTool],
    ) -> None:
        super().__init__()
        self._provider = provider
        self._prompt_builder = prompt_builder
        self._response_model = response_model
        self._allowed_tools = allowed_tools

    async def exec(self, state: State, context: ToolContext) -> State:
        request = self._prompt_builder.build(state)
        decision = await self._provider.complete(
            request,
            self._response_model,
        )
        self._validate_tool_calls(state, decision)
        return self.apply_decision(state, decision)

    def _validate_tool_calls(
        self,
        state: State,
        decision: DecisionT,
    ) -> None:
        available_tools = set(state.available_tools)
        if any(
            tool_call.tool_name not in available_tools
            or tool_call.tool_name not in self._allowed_tools
            for tool_call in decision.tool_calls
        ):
            raise AgentResponseFormatError()

    @abstractmethod
    def apply_decision(
        self,
        state: State,
        decision: DecisionT,
    ) -> State:
        ...


class PlanNode(LLMDecisionNode[PlanDecision]):
    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: AgentPromptBuilder,
        allowed_tools: frozenset[AvailableTool],
    ) -> None:
        super().__init__(
            provider=provider,
            prompt_builder=prompt_builder,
            response_model=PlanDecision,
            allowed_tools=allowed_tools,
        )

    def apply_decision(
        self,
        state: State,
        decision: PlanDecision,
    ) -> State:
        new_state = state.model_copy(deep=True)
        if decision.next_action == Action.CLARIFY:
            new_state.messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    content=decision.content,
                )
            )
        new_state.phase = AgentPhase.PLANNING
        new_state.info = decision.info
        new_state.draft = decision.draft
        new_state.next_action = decision.next_action
        new_state.pending_tool_calls = decision.tool_calls
        return new_state


class ReviewNode(LLMDecisionNode[ReviewDecision]):
    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: AgentPromptBuilder,
        allowed_tools: frozenset[AvailableTool],
    ) -> None:
        super().__init__(
            provider=provider,
            prompt_builder=prompt_builder,
            response_model=ReviewDecision,
            allowed_tools=allowed_tools,
        )

    def apply_decision(
        self,
        state: State,
        decision: ReviewDecision,
    ) -> State:
        new_state = state.model_copy(deep=True)
        new_state.phase = AgentPhase.REVIEWING
        new_state.review = decision.report
        new_state.next_action = decision.next_action
        new_state.pending_tool_calls = decision.tool_calls
        if decision.next_action == Action.REPLAN:
            new_state.revision_count += 1
        return new_state


class ClarifyNode(Node):
    async def exec(self, state: State, context: ToolContext) -> State:
        return state


class ConfirmNode(Node):
    async def exec(self, state: State, context: ToolContext) -> State:
        new_state = state.model_copy(deep=True)
        message_parts = ["计划已完成自动评审，请确认是否采用。"]
        if state.review is not None:
            message_parts.append(f"评审摘要：{state.review.summary}")
            visible_findings = state.review.findings[:5]
            if visible_findings:
                message_parts.append("需要留意：")
                message_parts.extend(
                    f"- {finding.description}"
                    for finding in visible_findings
                )

        new_state.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content="\n".join(message_parts)[:5000],
            )
        )
        new_state.phase = AgentPhase.AWAITING_CONFIRMATION
        new_state.human_decision = None
        new_state.next_action = Action.PAUSE
        new_state.pending_tool_calls = []
        return new_state


class ToolNode(Node):
    def __init__(
        self,
        return_action: Action,
        phase: AgentPhase,
    ) -> None:
        super().__init__()
        self._return_action = return_action
        self._phase = phase

    async def exec(self, state: State, context: ToolContext) -> State:
        new_state = state.model_copy(deep=True)
        results: list[ToolResult] = []

        for tool_call in state.pending_tool_calls:
            definition = get_tool_definition(tool_call.tool_name)
            try:
                arguments = definition.input_schema.model_validate(
                    tool_call.parameter
                )
                output = await definition.handler(context, arguments)
                results.append(
                    ToolResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        arguments=tool_call.parameter,
                        phase=self._phase,
                        status=ToolResultStatus.SUCCESS,
                        output=jsonable_encoder(output),
                    )
                )
            except ValidationError as exc:
                results.append(
                    ToolResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        arguments=tool_call.parameter,
                        phase=self._phase,
                        status=ToolResultStatus.ERROR,
                        error=ToolError(
                            code="invalid_tool_arguments",
                            message=str(exc),
                            retryable=True,
                        ),
                    )
                )
            except AppError as exc:
                if exc.status_code >= 500:
                    raise
                results.append(
                    ToolResult(
                        call_id=tool_call.call_id,
                        tool_name=tool_call.tool_name,
                        arguments=tool_call.parameter,
                        phase=self._phase,
                        status=ToolResultStatus.ERROR,
                        error=ToolError(
                            code=type(exc).__name__,
                            message=exc.message,
                        ),
                    )
                )

        new_state.tool_results.extend(results)
        new_state.phase = self._phase
        new_state.pending_tool_calls = []
        new_state.next_action = self._return_action
        return new_state
