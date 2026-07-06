from unittest.mock import AsyncMock

from dependencies.agent import get_agent_flow
from exceptions.agent import AgentSessionNotFoundError
from main import app
from schemas.agent import AgentTurnRequest


def test_resume_agent_session_not_found_returns_404(
    client,
    fake_user,
    fake_db,
    monkeypatch,
):
    fake_flow = object()

    async def override_get_agent_flow():
        return fake_flow

    app.dependency_overrides[get_agent_flow] = override_get_agent_flow

    mock_service = AsyncMock(
        side_effect=AgentSessionNotFoundError(),
    )
    monkeypatch.setattr(
        "router.agent.resume_agent_session_by_session_id_for_user",
        mock_service,
    )

    response = client.patch(
        "/api/agent/",
        params={"session_id": 1},
        json={"message": "继续规划"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "message": "Agent 会话不存在",
        "data": None,
    }
    mock_service.assert_awaited_once_with(
        AgentTurnRequest(message="继续规划"),
        1,
        fake_user.user_id,
        fake_db,
        fake_flow,
    )
