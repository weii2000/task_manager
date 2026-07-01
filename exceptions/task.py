from exceptions.base import AppError


class TaskNotFoundError(AppError):
    status_code = 404
    default_message = "任务不存在"


class EmptyTaskUpdateError(AppError):
    status_code = 400
    default_message = "没有需要更新的任务信息"