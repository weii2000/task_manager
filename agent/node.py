import json
from typing import Any

from fastapi.encoders import jsonable_encoder

from agent.provider import LLMProvider
from agent.state import AvailableTool, Message, MessageRole, ResponseMessage, State, ToolCall
from agent.tools.base import ToolContext
from agent.tools.registry import get_tool_handler


class Node():
    def __init__(self) -> None:
        self.successors: dict[str, Node] = {}
        self._action = "default"

    async def exec(self, state: State, context: ToolContext) -> State:
        raise NotImplementedError
    
    def __rshift__(self, other):
        self.successors[self._action] = other
        self._action = "default"
        return other
    
    def __sub__(self, action: str):
        self._action = action or "default"
        return self
    

class ThinkNode(Node):
    def __init__(self, provider: LLMProvider) -> None:
        super().__init__()
        self._provider = provider

    async def exec(self, state: State, context: ToolContext) -> State:
        return await self._provider.complete(state)


class ClarifyNode(Node):
    async def exec(self, state: State, context: ToolContext) -> State:
        return state


class ToolNode(Node):
    async def exec(self, state: State, context: ToolContext) -> State:
        assert isinstance(state.messages[-1], ResponseMessage)
        tool_calls: list[ToolCall] = state.messages[-1].tool_calls
        new_state = state.model_copy(deep=True)
        tool_results: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            tool_result = await get_tool_handler(tool_call.tool_name)(context, tool_call.parameter)

            tool_results.append(
                {
                    "tool_name": tool_call.tool_name,
                    "result": jsonable_encoder(tool_result),
                }
            )

        new_state.messages.append(Message(role=MessageRole.TOOL, content=json.dumps(tool_results, ensure_ascii=False)))

        return new_state

        
    
