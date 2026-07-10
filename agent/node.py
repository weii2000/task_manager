from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from agent.prompt import PromptBuilder
from agent.provider import LLMProvider
from agent.state import (
    Action,
    AgentDecision,
    Message,
    MessageRole,
    State,
    ToolError,
    ToolResult,
    ToolResultStatus,
)
from agent.tools.base import ToolContext
from agent.tools.registry import get_tool_definition
from exceptions.agent import AgentResponseFormatError
from exceptions.base import AppError


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


class ThinkNode(Node):
    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: PromptBuilder,
    ) -> None:
        super().__init__()
        self._provider = provider
        self._prompt_builder = prompt_builder

    async def exec(self, state: State, context: ToolContext) -> State:
        request = self._prompt_builder.build(state)
        decision = await self._provider.complete(request, AgentDecision)

        if any(
            tool_call.tool_name not in state.available_tools
            for tool_call in decision.tool_calls
        ):
            raise AgentResponseFormatError()

        new_state = state.model_copy(deep=True)
        new_state.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=decision.content,
            )
        )
        new_state.info = decision.info
        new_state.draft = decision.draft
        new_state.next_action = decision.next_action
        new_state.pending_tool_calls = decision.tool_calls
        return new_state


class ClarifyNode(Node):
    async def exec(self, state: State, context: ToolContext) -> State:
        return state


class ToolNode(Node):
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
                        status=ToolResultStatus.ERROR,
                        error=ToolError(
                            code=type(exc).__name__,
                            message=exc.message,
                        ),
                    )
                )

        new_state.tool_results.extend(results)
        new_state.pending_tool_calls = []
        new_state.next_action = Action.THINK
        return new_state
