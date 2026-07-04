from enum import StrEnum



class ProjectStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class ProjectSystemType(StrEnum):
    INBOX = "inbox"


class CreationSource(StrEnum):
    MANUAL = "manual"
    AGENT = "agent"
    SYSTEM = "system"


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
