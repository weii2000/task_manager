from exceptions.base import AppError


class TaskNotFoundError(AppError):
    status_code = 404
    default_message = "任务不存在"


class EmptyTaskUpdateError(AppError):
    status_code = 400
    default_message = "没有需要更新的任务信息"


class ParentTaskPlanMismatchError(AppError):
    status_code = 409
    default_message = "父任务与目标计划不一致"


class PlanUnavailableForTaskError(AppError):
    status_code = 409
    default_message = "当前计划不允许进行任务操作"


class InboxPlanNotFoundError(AppError):
    status_code = 500
    default_message = "用户默认计划不存在"


class ArchivedTaskModificationError(AppError):
    status_code = 409
    default_message = "归档任务需要恢复后才能修改"


class InvalidTaskTimeRangeError(AppError):
    status_code = 400
    default_message = "截止时间不能早于开始时间"


class InvalidTaskStatusTransitionError(AppError):
    status_code = 409
    default_message = "不允许进行该任务状态转换"


class IncompleteChildTasksError(AppError):
    status_code = 409
    default_message = "存在未完成的子任务，无法完成当前任务"


class TaskHasUnarchivedChildrenError(AppError):
    status_code = 409
    default_message = "存在未归档的子任务，无法归档当前任务"


class ParentTaskUnavailableError(AppError):
    status_code = 409
    default_message = "父任务当前不允许添加或恢复子任务"


class TaskLevelLimitExceededError(AppError):
    status_code = 409
    default_message = "任务层级不能超过三级"
