import enum


class DocumentLifecycleStatus(enum.StrEnum):
    DRAFT = "draft"
    WORKING = "working"
    FINAL = "final"
    ARCHIVED = "archived"
