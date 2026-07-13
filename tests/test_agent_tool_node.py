import asyncio
from unittest.mock import AsyncMock, MagicMock

from agent.context import AgentRunContext
from agent.node import ToolNode
from agent.state import (
    Action,
    AgentPhase,
    AvailableTool,
    Message,
    MessageRole,
    State,
    ToolCall,
    ToolResultStatus,
)
from agent.tools.registry import TOOL_REGISTRY


def make_context(*, in_transaction: bool = True) -> AgentRunContext:
    db = MagicMock()
    db.in_transaction.return_value = in_transaction
    db.rollback = AsyncMock()
    return AgentRunContext(user_id=1, db=db)


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
        result = asyncio.run(
            ToolNode(
                return_action=Action.PLAN,
                phase=AgentPhase.PLANNING,
            ).exec(state, make_context())
        )
    finally:
        object.__setattr__(definition, "handler", original_handler)

    handler.assert_not_awaited()
    assert result.pending_tool_calls == []
    assert result.next_action == Action.PLAN
    assert result.tool_results[0].phase == AgentPhase.PLANNING
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
        result = asyncio.run(
            ToolNode(
                return_action=Action.REVIEW,
                phase=AgentPhase.REVIEWING,
            ).exec(state, make_context())
        )
    finally:
        object.__setattr__(definition, "handler", original_handler)

    handler.assert_awaited_once()
    arguments = handler.await_args.args[1]
    assert arguments.project_id == 42
    assert result.tool_results[0].status == ToolResultStatus.SUCCESS
    assert result.next_action == Action.REVIEW
    assert result.tool_results[0].phase == AgentPhase.REVIEWING
    assert result.tool_results[0].output == {
        "project_id": 42,
        "task_tree": [],
    }


def test_tool_node_closes_transaction_it_started():
    definition = TOOL_REGISTRY[AvailableTool.LIST_USER_PROJECTS]
    original_handler = definition.handler
    handler = AsyncMock(return_value=[])
    object.__setattr__(definition, "handler", handler)
    context = make_context(in_transaction=False)
    context.db.in_transaction.side_effect = [False, True]
    state = State(
        messages=[Message(role=MessageRole.USER, content="查看项目")],
        next_action=Action.USE_TOOL,
        pending_tool_calls=[
            ToolCall(
                call_id="call-1",
                tool_name=AvailableTool.LIST_USER_PROJECTS,
                parameter={},
            )
        ],
    )

    try:
        asyncio.run(
            ToolNode(
                return_action=Action.PLAN,
                phase=AgentPhase.PLANNING,
            ).exec(state, context)
        )
    finally:
        object.__setattr__(definition, "handler", original_handler)

    context.db.rollback.assert_awaited_once()
