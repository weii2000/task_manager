from exceptions.base import AppError


class UsernameAlreadyExistsError(AppError):
    status_code = 409
    default_message = "用户名已存在"


class EmailAlreadyExistsError(AppError):
    status_code = 409
    default_message = "邮箱已被使用"


class UserNotFoundError(AppError):
    status_code = 404
    default_message = "用户不存在"


class EmptyUserUpdateError(AppError):
    status_code = 400
    default_message = "没有需要更新的用户资料"