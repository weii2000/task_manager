from exceptions.base import AppError


class AuthenticationError(AppError):
    status_code = 401
    headers = {"WWW-Authenticate": "Bearer"}


class InvalidCredentialsError(AuthenticationError):
    default_message = "用户名或密码错误"


class InvalidAccessTokenError(AuthenticationError):
    default_message = "登录状态无效或已过期"


class InvalidRefreshTokenError(AuthenticationError):
    default_message = "刷新凭证无效或已过期"