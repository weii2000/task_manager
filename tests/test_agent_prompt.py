import json

from agent.context import RetrievedMemory
from agent.flow import PLAN_ALLOWED_TOOLS, REVIEW_ALLOWED_TOOLS
from agent.prompt import PlanPromptBuilder, ReviewPromptBuilder
from agent.state import (
    Action,
    AgentPhase,
    AvailableTool,
    Message,
    MessageRole,
    ReviewReport,
    State,
    ToolCall,
    ToolResult,
    ToolResultStatus,
)
from models.enums import MemoryCategory


def get_context(request) -> dict[str, object]:
    context_content = request.messages[1].content
    return json.loads(context_content)["current_context"]


def test_plan_prompt_uses_history_and_planning_context():
    tool_call = ToolCall(
        call_id="call-1",
        tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
        parameter={"project_id": 42},
    )
    state = State(
        messages=[
            Message(role=MessageRole.USER, content="继续规划项目 42"),
            Message(
                role=MessageRole.ASSISTANT,
                content="我先查看已有任务。",
            ),
        ],
        pending_tool_calls=[tool_call],
        review=ReviewReport(summary="上一版缺少验收标准"),
        tool_results=[
            ToolResult(
                call_id="call-1",
                tool_name=AvailableTool.GET_PROJECT_TASK_TREE,
                arguments={"project_id": 42},
                phase=AgentPhase.PLANNING,
                status=ToolResultStatus.SUCCESS,
                output={"project_id": 42, "task_tree": []},
            )
        ],
    )

    request = PlanPromptBuilder(PLAN_ALLOWED_TOOLS).build(state)

    assert [message.role for message in request.messages] == [
        MessageRole.SYSTEM,
        MessageRole.SYSTEM,
        MessageRole.USER,
        MessageRole.ASSISTANT,
    ]
    context = get_context(request)

    assert "messages" not in context
    assert "next_action" not in context
    assert "pending_tool_calls" not in context
    assert context["previous_review"]["summary"] == (
        "上一版缺少验收标准"
    )
    assert context["recent_tool_results"][0]["call_id"] == "call-1"
    assert context["available_tools"][1]["input_schema"]["required"] == [
        "project_id"
    ]


def test_review_prompt_only_includes_review_tool_results():
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        tool_results=[
            ToolResult(
                call_id="plan-call",
                tool_name=AvailableTool.LIST_USER_PROJECTS,
                arguments={},
                phase=AgentPhase.PLANNING,
                status=ToolResultStatus.SUCCESS,
                output=[],
            ),
            ToolResult(
                call_id="review-call",
                tool_name=AvailableTool.LIST_USER_PROJECTS,
                arguments={},
                phase=AgentPhase.REVIEWING,
                status=ToolResultStatus.SUCCESS,
                output=[],
            ),
        ],
    )

    request = ReviewPromptBuilder(REVIEW_ALLOWED_TOOLS).build(state)
    context = get_context(request)

    assert context["recent_tool_results"] == [
        {
            "call_id": "review-call",
            "tool_name": "list_user_projects",
            "arguments": {},
            "phase": "reviewing",
            "status": "success",
            "output": [],
            "error": None,
        }
    ]


def test_prompt_includes_ephemeral_long_term_memory_context():
    state = State(
        messages=[Message(role=MessageRole.USER, content="规划学习")]
    )
    memory = RetrievedMemory(
        memory_id=12,
        category=MemoryCategory.PREFERENCE,
        content="用户偏好每个任务不超过一小时",
    )

    request = PlanPromptBuilder(PLAN_ALLOWED_TOOLS).build(
        state,
        (memory,),
    )
    context = get_context(request)

    assert context["long_term_memories"] == [
        {
            "memory_id": 12,
            "category": "preference",
            "content": "用户偏好每个任务不超过一小时",
        }
    ]
    assert "long_term_memories" not in state.model_dump()
