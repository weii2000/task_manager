from agent.node import ClarifyNode, ThinkNode, ToolNode
from agent.prompt import PromptBuilder
from agent.provider import LLMProvider
from agent.state import Action, State
from agent.tools.base import ToolContext
from exceptions.agent import AgentFlowStepLimitExceededError


class Flow:
    def __init__(
        self,
        provider: LLMProvider,
        max_steps: int = 20,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.max_steps = max_steps
        self.think_node = ThinkNode(
            provider,
            prompt_builder or PromptBuilder(),
        )
        self.clarify_node = ClarifyNode()
        self.tool_node = ToolNode()

        self.think_node - Action.CLARIFY.value >> self.clarify_node  # pyright: ignore[reportUnusedExpression]
        self.think_node - Action.USE_TOOL.value >> self.tool_node  # pyright: ignore[reportUnusedExpression]
        self.tool_node - Action.THINK.value >> self.think_node  # pyright: ignore[reportUnusedExpression]

    async def run(self, state: State, context: ToolContext) -> tuple[State, str]:
        cur = self.think_node
        steps = 0

        while cur:
            if steps >= self.max_steps:
                raise AgentFlowStepLimitExceededError()

            state = await cur.exec(state, context)
            steps += 1
            cur = cur.successors.get(state.next_action.value)

        return state, state.messages[-1].content
