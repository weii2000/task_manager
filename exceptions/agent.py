from exceptions.base import AppError


class AgentConfigurationError(AppError):
    status_code = 503
    default_message = "规划服务尚未正确配置"


class AgentUnavailableError(AppError):
    status_code = 503
    default_message = "规划服务暂时不可用，请稍后重试"


class AgentInvalidOutputError(AppError):
    status_code = 502
    default_message = "规划服务返回了无效结果"
