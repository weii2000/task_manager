from agent.provider import LLMProvider
from agent.state import State


class Node():
    def __init__(self) -> None:
        self.successors: dict[str, Node] = {}
        self._action = "default"

    async def exec(self, state: State) -> State:
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

    async def exec(self, state: State) -> State:
        return await self._provider.complete(state)


class ClarifyNode(Node):
    def __init__(self) -> None:
        super().__init__()
        # self.question = ""

    async def exec(self, state: State) -> State:
        # self.question = state.messages[-1].content
        return state


class ToolNode(Node):
    async def exec(self, payload: State) -> State:
        ...
    
