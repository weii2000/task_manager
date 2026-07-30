import json
from datetime import datetime, timezone

from agent.prompt import (
    PLAN_SYSTEM_PROMPT,
    REVIEW_SYSTEM_PROMPT,
    PlanPromptBuilder,
    ReviewPromptBuilder,
)
from agent.runtime.context import RetrievedMemory
from agent.runtime.flow import PLAN_ALLOWED_TOOLS, REVIEW_ALLOWED_TOOLS
from agent.runtime.state import (
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
        tool_name=AvailableTool.GET_PLAN_TASK_TREE,
        parameter={"plan_id": 42},
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
                tool_name=AvailableTool.GET_PLAN_TASK_TREE,
                arguments={"plan_id": 42},
                phase=AgentPhase.PLANNING,
                status=ToolResultStatus.SUCCESS,
                output={"plan_id": 42, "task_tree": []},
            )
        ],
    )

    fixed_time = datetime(2026, 7, 13, tzinfo=timezone.utc)
    request = PlanPromptBuilder(
        PLAN_ALLOWED_TOOLS,
        current_time_utc=fixed_time,
    ).build(state)

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
    assert context["current_time_utc"] == "2026-07-13T00:00:00Z"
    assert context["previous_review"]["summary"] == (
        "上一版缺少验收标准"
    )
    assert context["recent_tool_results"][0]["call_id"] == "call-1"
    assert context["available_tools"][1]["input_schema"]["required"] == [
        "plan_id"
    ]
    assert request.messages[2].content == "继续规划项目 42"


def test_review_prompt_includes_recent_tool_results_across_phases():
    state = State(
        messages=[Message(role=MessageRole.USER, content="帮我规划学习")],
        tool_results=[
            ToolResult(
                call_id="plan-call",
                tool_name=AvailableTool.LIST_USER_PLANS,
                arguments={},
                phase=AgentPhase.PLANNING,
                status=ToolResultStatus.SUCCESS,
                output=[],
            ),
            ToolResult(
                call_id="review-call",
                tool_name=AvailableTool.LIST_USER_PLANS,
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
            "call_id": "plan-call",
            "tool_name": "list_user_plans",
            "arguments": {},
            "phase": "planning",
            "status": "success",
            "output": [],
            "error": None,
        },
        {
            "call_id": "review-call",
            "tool_name": "list_user_plans",
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


def test_prompts_define_time_tool_and_review_action_contracts():
    assert "不得依赖模型记忆猜测当前日期" in PLAN_SYSTEM_PROMPT
    assert "必须优先选择 \"clarify\"" in PLAN_SYSTEM_PROMPT
    assert "相同工具和相同参数的成功结果时必须直接复用" in (
        PLAN_SYSTEM_PROMPT
    )
    assert "start_time 或 due_time 为 null 本身不是缺陷" in (
        REVIEW_SYSTEM_PROMPT
    )
    assert "没有 blocking finding 时选择 \"confirm\"" in (
        REVIEW_SYSTEM_PROMPT
    )
    assert "叶子任务缺少具体、可验证的 acceptance_criteria" in (
        REVIEW_SYSTEM_PROMPT
    )
