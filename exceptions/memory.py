from exceptions.base import AppError


class MemoryNotFoundError(AppError):
    status_code = 404
    default_message = "长期记忆不存在"


class ArchivedMemoryModificationError(AppError):
    status_code = 409
    default_message = "已归档的长期记忆不能修改"


class MemoryStateConflictError(AppError):
    status_code = 409
    default_message = "长期记忆已发生变化，请重试"


class MemoryResolutionError(AppError):
    status_code = 502
    default_message = "长期记忆服务返回无效结果"


class MemoryNotPendingError(AppError):
    status_code = 409
    default_message = "长期记忆当前不在等待确认状态"
