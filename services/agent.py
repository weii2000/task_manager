from agent.flow import run_planning_flow
from agent.provider import (
    PlanningProvider,
    PlanningProviderConfigurationError,
    PlanningProviderInvalidOutputError,
    PlanningProviderUnavailableError,
)
from agent.state import PlanningState
from exceptions.agent import (
    AgentConfigurationError,
    AgentInvalidOutputError,
    AgentUnavailableError,
)
from schemas.agent import PlanningTurnRequest


async def run_planning_turn_for_user(
    turn_request: PlanningTurnRequest,
    provider: PlanningProvider,
) -> PlanningState:
    try:
        return await run_planning_flow(
            state=turn_request.state,
            user_message=turn_request.message,
            provider=provider,
        )
    except PlanningProviderConfigurationError as exc:
        raise AgentConfigurationError() from exc
    except PlanningProviderUnavailableError as exc:
        raise AgentUnavailableError() from exc
    except PlanningProviderInvalidOutputError as exc:
        raise AgentInvalidOutputError() from exc
