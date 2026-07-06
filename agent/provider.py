import json
from json import JSONDecodeError
from typing import Any, Protocol

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from agent.state import MessageRole, PlanningDraft, PlanningInfo, ResponseMessage, State
from exceptions.agent import AgentProviderError, AgentResponseFormatError


SYSTEM_PROMPT = """
你是 Task Manager 项目中的任务规划 Agent。

你的任务是根据当前 State，帮助用户把目标逐步澄清成一个项目规划草稿。
最终草稿应该包含任务以及必要的子任务。

你每次都会收到一个 JSON 格式的 State，里面包含：
- messages：当前会话历史
- available_tools：当前可用工具列表
- info：已经抽取出的规划信息
- draft：当前计划草稿

你必须只返回一个合法 JSON 对象，不要输出 Markdown，不要输出额外解释。

返回 JSON 必须包含以下字段：

{
  "content": "给用户看的回复内容",
  "next_action": "clarify | use_tool | finish",
  "tool_calls": [],
  "info": {
    "goal": null,
    "acceptance_criteria": null,
    "constraints": null
  },
  "draft": {
    "tasks": []
  }
}

字段规则：

1. content
- 如果 next_action 是 "clarify"，content 必须是一个具体、清晰、容易回答的追问。
- 如果 next_action 是 "use_tool"，content 必须简短说明为什么需要调用工具。
- 如果 next_action 是 "finish"，content 必须是面向用户的计划草稿总结。

2. next_action
- 如果信息不足，返回 "clarify"。
- 如果需要调用工具，返回 "use_tool"。
- 如果信息足够并且已经形成可执行计划，返回 "finish"。

3. tool_calls
- 如果 next_action 不是 "use_tool"，必须返回空数组 []。
- 如果 next_action 是 "use_tool"，返回需要调用的工具列表。
- 每个工具调用格式必须是：
  {
    "tool_name": "工具名称",
    "parameter": {}
  }

4. info
- 返回你根据当前 State 更新后的完整 info。
- 不知道的信息使用 null。
- constraints 如果不知道，使用 null；如果用户明确没有限制，使用 []。

5. draft
- 必须始终返回对象，不能返回 null。
- 如果还没有草稿，返回 {"tasks": []}。
- 每个任务格式必须是：
  {
    "title": "任务标题",
    "description": "任务说明",
    "start_time": null,
    "due_time": null,
    "subtasks": []
  }

行为规则：
- 使用简体中文。
- 不要编造用户没有提供的重要约束。
- 信息不足时，一次只问一个最关键的问题。
- 不要声称已经创建、保存或修改真实项目或任务，除非工具结果明确表明已经完成。
- 当前如果 available_tools 为空，不要选择 "use_tool"。
- 返回内容必须能被 Python 的 json.loads 直接解析。
""".strip()

SYSTEM_PROMPT_MESSAGE = {"role": MessageRole.SYSTEM, "content": SYSTEM_PROMPT}

class LLMProvider(Protocol):
    async def complete(self, state: State) -> State:
        ...


class OpenAICompatibleLLMProvider:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )
    
    async def complete(self, state: State) -> State:
        state_json = state.model_dump_json()
        messages = [SYSTEM_PROMPT_MESSAGE, {"role": MessageRole.USER, "content": state_json}]
        kwargs = {"model": self._model, "messages": messages}
        try:
            completion = await self._client.chat.completions.create(**kwargs)
            raw_content = completion.choices[0].message.content
            if raw_content is None:
                raise AgentResponseFormatError()

            response_msg: dict[str, Any] = {"role": MessageRole.ASSISTANT}
            response_dict = json.loads(raw_content)
            response_state = state.model_copy(deep=True)
            response_msg["content"] = response_dict["content"]
            response_msg["next_action"] = response_dict["next_action"]
            response_msg["tool_calls"] = response_dict["tool_calls"]
            response_state.messages.append(ResponseMessage.model_validate(response_msg))
            response_state.info = PlanningInfo.model_validate(response_dict["info"])
            response_state.draft = PlanningDraft.model_validate(response_dict["draft"])
            return response_state
        except AgentResponseFormatError:
            raise
        except (JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise AgentResponseFormatError() from exc
        except OpenAIError as exc:
            raise AgentProviderError() from exc


        
