import enum


class ContractStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVAL = "approval"
    SIGNED = "signed"
    IN_PROGRESS = "in_progress"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ARCHIVED = "archived"


class ContractAddendumStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVAL = "approval"
    SIGNED = "signed"
    CANCELLED = "cancelled"
