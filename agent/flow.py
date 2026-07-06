from agent.nodes import (
    add_user_message_node,
    planning_model_node,
)
from agent.provider import PlanningProvider
from agent.state import PlanningState


async def run_planning_flow(
    state: PlanningState,
    user_message: str,
    provider: PlanningProvider,
) -> PlanningState:
    state_with_user_message = add_user_message_node(
        state,
        user_message,
    )

    updated_state = await planning_model_node(
        state_with_user_message,
        provider,
    )

    return updated_state
