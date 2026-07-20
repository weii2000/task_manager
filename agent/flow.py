from agent.context import AgentRunContext
from agent.executor import DatabasePlanExecutor, PlanExecutor
from agent.memory import MemoryManager
from agent.node import (
    ClarifyNode,
    ConfirmNode,
    ExecuteNode,
    Node,
    PlanNode,
    ReviewNode,
    ToolNode,
)
from agent.prompt import (
    AgentPromptBuilder,
    PlanPromptBuilder,
    ReviewPromptBuilder,
)
from agent.provider import LLMProvider
from agent.state import Action, AgentPhase, AvailableTool, State
from exceptions.agent import (
    AgentFlowEntryPointError,
    AgentFlowStepLimitExceededError,
)


PLAN_ALLOWED_TOOLS = frozenset(AvailableTool)
REVIEW_ALLOWED_TOOLS = frozenset(AvailableTool)


class Flow:
    def __init__(
        self,
        provider: LLMProvider,
        max_steps: int = 20,
        plan_prompt_builder: AgentPromptBuilder | None = None,
        review_prompt_builder: AgentPromptBuilder | None = None,
        executor: PlanExecutor | None = None,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.memory_manager = (
            memory_manager or MemoryManager(provider)
        )
        self.plan_node = PlanNode(
            provider=provider,
            prompt_builder=(
                plan_prompt_builder
                or PlanPromptBuilder(PLAN_ALLOWED_TOOLS)
            ),
            allowed_tools=PLAN_ALLOWED_TOOLS,
        )
        self.review_node = ReviewNode(
            provider=provider,
            prompt_builder=(
                review_prompt_builder
                or ReviewPromptBuilder(REVIEW_ALLOWED_TOOLS)
            ),
            allowed_tools=REVIEW_ALLOWED_TOOLS,
        )
        self.clarify_node = ClarifyNode()
        self.confirm_node = ConfirmNode()
        self.execute_node = ExecuteNode(
            executor if executor is not None else DatabasePlanExecutor()
        )
        self.plan_tool_node = ToolNode(
            return_action=Action.PLAN,
            phase=AgentPhase.PLANNING,
        )
        self.review_tool_node = ToolNode(
            return_action=Action.REVIEW,
            phase=AgentPhase.REVIEWING,
        )

        self.plan_node - Action.CLARIFY.value >> self.clarify_node  # pyright: ignore[reportUnusedExpression]
        self.plan_node - Action.USE_TOOL.value >> self.plan_tool_node  # pyright: ignore[reportUnusedExpression]
        self.plan_node - Action.REVIEW.value >> self.review_node  # pyright: ignore[reportUnusedExpression]
        self.plan_tool_node - Action.PLAN.value >> self.plan_node  # pyright: ignore[reportUnusedExpression]

        self.review_node - Action.USE_TOOL.value >> self.review_tool_node  # pyright: ignore[reportUnusedExpression]
        self.review_node - Action.REPLAN.value >> self.plan_node  # pyright: ignore[reportUnusedExpression]
        self.review_node - Action.CONFIRM.value >> self.confirm_node  # pyright: ignore[reportUnusedExpression]
        self.review_tool_node - Action.REVIEW.value >> self.review_node  # pyright: ignore[reportUnusedExpression]

        self.entry_nodes: dict[Action, Node] = {
            Action.PLAN: self.plan_node,
            Action.EXECUTE: self.execute_node,
        }

    async def run(
        self,
        state: State,
        context: AgentRunContext,
    ) -> tuple[State, str]:
        state = State.model_validate(state.model_dump()) # 执行pydantic校验，确保状态合法
        next_action = state.next_action
        if next_action is None:
            raise AgentFlowEntryPointError()

        if next_action == Action.PLAN:
            state = await self.memory_manager.compact(state)
            state = State.model_validate(state.model_dump())

        cur = self.entry_nodes.get(next_action)
        if cur is None:
            raise AgentFlowEntryPointError()
        steps = 0

        while cur:
            if steps >= self.max_steps:
                raise AgentFlowStepLimitExceededError()

            state = await cur.exec(state, context)
            state = State.model_validate(state.model_dump())
            steps += 1
            next_action = state.next_action
            cur = (
                cur.successors.get(next_action.value)
                if next_action is not None
                else None
            )

        return state, state.messages[-1].content
