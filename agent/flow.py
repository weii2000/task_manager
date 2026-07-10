from agent.executor import DatabasePlanExecutor, PlanExecutor
from agent.node import (
    ClarifyNode,
    ConfirmNode,
    ExecuteNode,
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
from agent.tools.base import ToolContext
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
    ) -> None:
        self.max_steps = max_steps
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

        self.entry_nodes = {
            Action.PLAN: self.plan_node,
            Action.EXECUTE: self.execute_node,
        }

    async def run(
        self,
        state: State,
        context: ToolContext,
    ) -> tuple[State, str]:
        cur = self.entry_nodes.get(state.next_action)
        if cur is None:
            raise AgentFlowEntryPointError()
        steps = 0

        while cur:
            if steps >= self.max_steps:
                raise AgentFlowStepLimitExceededError()

            state = await cur.exec(state, context)
            steps += 1
            cur = cur.successors.get(state.next_action.value)

        return state, state.messages[-1].content
