from typing import Annotated

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

from core.config import settings
from core.security import decode_token
from crud.user import get_user_by_user_id
from database.session import AsyncSessionLocal
from schemas.plan_tree import PlanResult, PlanTreeCreate
from services.plan_tree import create_plan_tree_for_user

CREATE_PLAN_SCOPE = "plans:create"


class PlanwiseTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        subject = decode_token(token, "access")
        if subject is None:
            return None
        try:
            user_id = int(subject)
        except ValueError:
            return None

        async with AsyncSessionLocal() as db:
            if await get_user_by_user_id(user_id, db) is None:
                return None

        return AccessToken(
            token=token,
            client_id="planwise",
            scopes=[CREATE_PLAN_SCOPE],
            subject=subject,
        )


mcp_server = MCPServer(
    name="planwise",
    description="Create a plan and its complete task tree.",
    version="1.0.0",
    token_verifier=PlanwiseTokenVerifier(),
    auth=AuthSettings(
        issuer_url=settings.MCP_ISSUER_URL,
        resource_server_url=settings.MCP_RESOURCE_SERVER_URL,
        required_scopes=[CREATE_PLAN_SCOPE],
    ),
)


@mcp_server.tool(
    name="create_plan",
    description=(
        "Create one plan and its complete nested task tree atomically. "
        "Reuse the same idempotency_key when retrying the same plan."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def create_plan(
    idempotency_key: Annotated[str, Field(min_length=1, max_length=64)],
    plan: PlanTreeCreate,
) -> PlanResult:
    access_token = get_access_token()
    if access_token is None or access_token.subject is None:
        raise RuntimeError("Authenticated user is missing")

    try:
        user_id = int(access_token.subject)
    except ValueError as exc:
        raise RuntimeError("Authenticated user is invalid") from exc

    idempotency_key = idempotency_key.strip()
    if not idempotency_key:
        raise ValueError("幂等键不能为空")

    async with AsyncSessionLocal() as db:
        return await create_plan_tree_for_user(
            plan,
            idempotency_key,
            user_id,
            db,
        )


mcp_http_app = mcp_server.streamable_http_app(
    json_response=True,
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=[
            settings.MCP_RESOURCE_SERVER_URL.host,
            f"{settings.MCP_RESOURCE_SERVER_URL.host}:*",
        ],
    ),
)
