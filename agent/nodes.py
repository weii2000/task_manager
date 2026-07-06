from agent.provider import (
    PlanningAction,
    PlanningProvider,
)
from agent.state import (
    MessageRole,
    PlanningMessage,
    PlanningPhase,
    PlanningState,
)


def add_user_message_node(
    state: PlanningState,
    user_message: str,
) -> PlanningState:
    message = PlanningMessage(
        role=MessageRole.USER,
        content=user_message,
    )

    return PlanningState(
        messages=[
            *state.messages,
            message,
        ],
        info=state.info,
        phase=state.phase,
        draft=state.draft,
    )


async def planning_model_node(
    state: PlanningState,
    provider: PlanningProvider,
) -> PlanningState:
    output = await provider.run_turn(state)

    assistant_message = PlanningMessage(
        role=MessageRole.ASSISTANT,
        content=output.message,
    )

    messages = [
        *state.messages,
        assistant_message,
    ]

    if output.action == PlanningAction.ASK:
        return PlanningState(
            messages=messages,
            info=output.info,
            phase=PlanningPhase.CLARIFYING,
            draft=None,
        )

    return PlanningState(
        messages=messages,
        info=output.info,
        phase=PlanningPhase.DRAFT_READY,
        draft=output.draft,
    )
