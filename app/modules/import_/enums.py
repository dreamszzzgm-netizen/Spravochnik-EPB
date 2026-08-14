import enum


class ImportSessionStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PREVIEW_READY = "preview_ready"
    CONFIRMED = "confirmed"
    APPLYING = "applying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CandidateStatus(enum.StrEnum):
    NEW = "new"
    UPDATE = "update"
    POTENTIAL_DUPLICATE = "potential_duplicate"
    CONFLICT = "conflict"
    ERROR = "error"
    SKIP = "skip"


class CandidateAction(enum.StrEnum):
    CREATE = "create"
    UPDATE = "update"
    SKIP = "skip"
    RESOLVE_CONFLICT = "resolve_conflict"
