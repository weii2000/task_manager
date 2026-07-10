from pydantic import BaseModel, ConfigDict, Field

from agent.state import HumanDecision, State


class AgentSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    state: State


class AgentTurnResponse(BaseModel):
    session: AgentSessionRead
    response: str = Field(min_length=1, max_length=5000)


class AgentTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class AgentConfirmRequest(HumanDecision):
    pass
