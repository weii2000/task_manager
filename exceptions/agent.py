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


class AgentSessionStateConflictError(AppError):
    status_code = 409
    default_message = "Agent 会话已被其他请求更新，请重试"


class InvalidAgentExecutionStateError(AppError):
    status_code = 409
    default_message = "Agent 会话当前不可执行"


class AgentExecutionNotApprovedError(AppError):
    status_code = 409
    default_message = "计划尚未获得人工批准"


class AgentExecutionContextError(AppError):
    status_code = 500
    default_message = "Agent 执行上下文无效"


class AgentResponseFormatError(AppError):
    status_code = 502
    default_message = "Agent 返回格式无效，请稍后重试"


class AgentProviderError(AppError):
    status_code = 502
    default_message = "Agent 服务暂时不可用，请稍后重试"


class AgentFlowStepLimitExceededError(AppError):
    status_code = 500
    default_message = "Agent 执行步骤超出限制"


class AgentFlowEntryPointError(AppError):
    status_code = 500
    default_message = "Agent 流程入口状态无效"
