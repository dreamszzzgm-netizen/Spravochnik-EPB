import enum


class TaskStatus(enum.StrEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskLinkKind(enum.StrEnum):
    ORGANIZATION = "organization"
    CONTRACT = "contract"
    CONTRACT_ITEM = "contract_item"
    TECHNICAL_DEVICE = "technical_device"
    BUILDING = "building"
    OPO = "opo"
