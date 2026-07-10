import json

from agent.prompt import PromptBuilder
from agent.state import (
    Action,
    AvailableTool,
    Message,
    MessageRole,
    State,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)


def test_prompt_uses_native_history_and_structured_context():
    tool_call = ToolCall(
        call_id="call-1",
        tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
        parameter={"project_id": 42},
    )
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="继续规划项目 42"),
            Message(role=MessageRole.ASSISTANT, content="我先查看已有任务。"),
        ],
        next_action=Action.THINK,
        pending_tool_calls=[tool_call],
        tool_results=[
            ToolResult(
                call_id="call-1",
                tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
                arguments={"project_id": 42},
                status=ToolResultStatus.SUCCESS,
                output={"project_id": 42, "task_tree": []},
            )
        ],
    )

    request = PromptBuilder().build(state)

    assert [message.role for message in request.messages] == [
        MessageRole.SYSTEM,
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    context_content = request.messages[1].content
    context_json = context_content.removeprefix(
        "<current_context>\n"
    ).removesuffix("\n</current_context>")
    context = json.loads(context_json)

    assert "messages" not in context
    assert "next_action" not in context
    assert "pending_tool_calls" not in context
    assert context["recent_tool_results"][0]["call_id"] == "call-1"
    assert context["available_tools"][1]["input_schema"]["required"] == [
        "project_id"
    ]
