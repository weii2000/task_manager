import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import mcp_server as mcp_module
from core.security import create_access_token
from mcp_server import (
    CREATE_PLAN_SCOPE,
    PlanwiseTokenVerifier,
    mcp_server,
)
from schemas.plan_tree import PlanResult


def test_mcp_exposes_only_create_plan():
    tools = asyncio.run(mcp_server.list_tools())

    assert [tool.name for tool in tools] == ["create_plan"]


def test_mcp_rejects_missing_token(client):
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2026-07-28",
                "capabilities": {},
            },
        },
    )

    assert response.status_code == 401


def test_mcp_token_verifier_accepts_existing_access_token(monkeypatch):
    monkeypatch.setattr(
        mcp_module,
        "get_user_by_user_id",
        AsyncMock(return_value=SimpleNamespace(user_id=7)),
    )

    access_token = asyncio.run(
        PlanwiseTokenVerifier().verify_token(
            create_access_token("7")
        )
    )

    assert access_token is not None
    assert access_token.subject == "7"
    assert access_token.scopes == [CREATE_PLAN_SCOPE]


def test_mcp_token_verifier_rejects_invalid_token():
    access_token = asyncio.run(
        PlanwiseTokenVerifier().verify_token("invalid-token")
    )

    assert access_token is None


def test_mcp_calls_service_with_authenticated_user(
    client,
    monkeypatch,
):
    service = AsyncMock(
        return_value=PlanResult(
            plan_id=42,
            plan_title="Demo",
            created_task_count=1,
        )
    )
    monkeypatch.setattr(
        mcp_module,
        "get_user_by_user_id",
        AsyncMock(return_value=SimpleNamespace(user_id=7)),
    )
    monkeypatch.setattr(
        mcp_module,
        "create_plan_tree_for_user",
        service,
    )
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_plan",
            "arguments": {
                "idempotency_key": "plan-1",
                "plan": {
                    "title": "Demo",
                    "tasks": [
                        {
                            "title": "First task",
                            "level": 1,
                        }
                    ],
                }
            },
        },
    }
    headers = {
        "Authorization": f"Bearer {create_access_token('7')}",
        "Mcp-Method": "tools/call",
        "Mcp-Name": "create_plan",
        "Mcp-Protocol-Version": "2025-11-25",
        "Host": "127.0.0.1:8000",
    }

    response = client.post(
        "/mcp",
        json=request,
        headers=headers,
    )

    assert response.status_code == 200
    result = response.json()["result"]["structuredContent"]
    assert result == {
        "plan_id": 42,
        "plan_title": "Demo",
        "created_task_count": 1,
    }
    assert service.await_args.args[0].title == "Demo"
    assert service.await_args.args[1] == "plan-1"
    assert service.await_args.args[2] == 7
