from exceptions.base import AppError


class PlanNotFoundError(AppError):
    status_code = 404
    default_message = "计划不存在"


class EmptyPlanUpdateError(AppError):
    status_code = 400
    default_message = "没有需要更新的计划信息"


class SystemPlanModificationError(AppError):
    status_code = 403
    default_message = "系统计划不允许修改"


class InvalidPlanTimeRangeError(AppError):
    status_code = 400
    default_message = "截止时间不能早于开始时间"


class InvalidPlanStatusTransitionError(AppError):
    status_code = 409
    default_message = "不允许进行该计划状态转换"


class ArchivedPlanModificationError(AppError):
    status_code = 409
    default_message = "归档计划需要恢复后才能修改"


class IncompletePlanTasksError(AppError):
    status_code = 409
    default_message = "存在未完成的任务，无法完成当前计划"
