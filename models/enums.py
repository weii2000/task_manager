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


class MemoryCategory(StrEnum):
    PROFILE = "profile"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"
    LONG_TERM_GOAL = "long_term_goal"


class MemoryStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


class MemorySource(StrEnum):
    MANUAL = "manual"
    CONVERSATION = "conversation"
