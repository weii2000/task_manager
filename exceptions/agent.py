from exceptions.base import AppError


class AgentSessionNotFoundError(AppError):
    status_code = 404
    default_message = "Agent 会话不存在"


class AgentSessionNotAwaitingConfirmationError(AppError):
    status_code = 409
    default_message = "Agent 会话当前不在等待确认状态"


class AgentSessionNotAcceptingTurnError(AppError):
    status_code = 409
    default_message = "Agent 会话当前不接受新的规划消息"


class AgentResponseFormatError(AppError):
    status_code = 502
    default_message = "Agent 返回格式无效，请稍后重试"


class AgentProviderError(AppError):
    status_code = 502
    default_message = "Agent 服务暂时不可用，请稍后重试"


class AgentFlowStepLimitExceededError(AppError):
    status_code = 500
    default_message = "Agent 执行步骤超出限制"
