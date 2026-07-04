from exceptions.base import AppError


class ProjectNotFoundError(AppError):
    status_code = 404
    default_message = "项目不存在"


class EmptyProjectUpdateError(AppError):
    status_code = 400
    default_message = "没有需要更新的项目信息"


class SystemProjectModificationError(AppError):
    status_code = 403
    default_message = "系统项目不允许修改"


class InvalidProjectTimeRangeError(AppError):
    status_code = 400
    default_message = "截止时间不能早于开始时间"


class InvalidProjectStatusTransitionError(AppError):
    status_code = 409
    default_message = "不允许进行该项目状态转换"


class ArchivedProjectModificationError(AppError):
    status_code = 409
    default_message = "归档项目需要恢复后才能修改"


class IncompleteProjectTasksError(AppError):
    status_code = 409
    default_message = "存在未完成的任务，无法完成当前项目"
