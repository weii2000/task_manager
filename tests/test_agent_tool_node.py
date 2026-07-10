import asyncio
from unittest.mock import AsyncMock

from agent.node import ToolNode
from agent.state import (
    Action,
    AvailableTool,
    Message,
    MessageRole,
    State,
    ToolCall,
    ToolResultStatus,
)
from agent.tools.base import ToolContext
from agent.tools.registry import TOOL_REGISTRY


def make_context() -> ToolContext:
    return ToolContext(user_id=1, db=AsyncMock())


def test_tool_node_validates_arguments_before_handler():
    definition = TOOL_REGISTRY[AvailableTool.GET_PROJECT_TASK_TREE]
    original_handler = definition.handler
    handler = AsyncMock()
    object.__setattr__(definition, "handler", handler)
    state = State(
        messages=[Message(role=MessageRole.USER, content="查看项目")],
        next_action=Action.USE_TOOL,
        pending_tool_calls=[
            ToolCall(
                call_id="call-1",
                tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
                parameter={},
            )
        ],
    )

    try:
        result = asyncio.run(ToolNode().exec(state, make_context()))
    finally:
        object.__setattr__(definition, "handler", original_handler)

    handler.assert_not_awaited()
    assert result.pending_tool_calls == []
    assert result.next_action == Action.THINK
    assert result.tool_results[0].status == ToolResultStatus.ERROR
    assert result.tool_results[0].error is not None
    assert result.tool_results[0].error.code == "invalid_tool_arguments"


def test_tool_node_records_successful_result():
    definition = TOOL_REGISTRY[AvailableTool.GET_PROJECT_TASK_TREE]
    original_handler = definition.handler
    handler = AsyncMock(
        return_value={"project_id": 42, "task_tree": []}
    )
    object.__setattr__(definition, "handler", handler)
    state = State(
        messages=[Message(role=MessageRole.USER, content="查看项目")],
        next_action=Action.USE_TOOL,
        pending_tool_calls=[
            ToolCall(
                call_id="call-1",
                tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
                parameter={"project_id": 42},
            )
        ],
    )

    try:
        result = asyncio.run(ToolNode().exec(state, make_context()))
    finally:
        object.__setattr__(definition, "handler", original_handler)

    handler.assert_awaited_once()
    arguments = handler.await_args.args[1]
    assert arguments.project_id == 42
    assert result.tool_results[0].status == ToolResultStatus.SUCCESS
    assert result.tool_results[0].output == {
        "project_id": 42,
        "task_tree": [],
    }
