from agent.node import ClarifyNode, Node, ThinkNode, ToolNode
from agent.provider import LLMProvider, OpenAICompatibleLLMProvider
from agent.state import Action, Message, MessageRole, PlanningDraft, PlanningInfo, State
from agent.tools.base import ToolContext
from exceptions.agent import AgentFlowStepLimitExceededError


class Flow:
    def __init__(self, provider: LLMProvider, max_steps: int = 20) -> None:
        self.max_steps = max_steps
        self.think_node = ThinkNode(provider)
        self.clarify_node = ClarifyNode()
        self.tool_node = ToolNode()

        self.think_node - Action.CLARIFY.value >> self.clarify_node # pyright: ignore[reportUnusedExpression]
        self.clarify_node - Action.THINK.value >> self.think_node # pyright: ignore[reportUnusedExpression]
        self.think_node - Action.USE_TOOL.value >> self.tool_node # pyright: ignore[reportUnusedExpression]
        self.tool_node - Action.THINK.value >> self.think_node # pyright: ignore[reportUnusedExpression]

    async def run(self, state: State, context: ToolContext) -> tuple[State, str]:
        cur = self.think_node
        steps = 0

        while cur:
            if steps >= self.max_steps:
                raise AgentFlowStepLimitExceededError()

            state = await cur.exec(state, context)
            steps += 1
            cur = cur.successors.get(getattr(state.messages[-1], "next_action", Action.THINK).value, None)

        return state, state.messages[-1].content




# async def main():
#     state = State(messages=[Message(role=MessageRole.USER, content="你是谁？")], info=PlanningInfo(), draft=PlanningDraft())
#     deepseek_provider = OpenAICompatibleLLMProvider(
#         api_key=settings.OPENAI_API_KEY.get_secret_value(),
#         base_url=settings.OPENAI_BASE_URL,
#         model=settings.OPENAI_MODEL,
#     )
#     think_node = ThinkNode(deepseek_provider)
#     flow = Flow(think_node)

#     await flow.run(state)


# if __name__ == "__main__":
#     asyncio.run(main())
