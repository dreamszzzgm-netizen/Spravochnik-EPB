# ruff: noqa

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.modules.documents.enums import DocumentLifecycleStatus
from app.modules.documents.models import Document, DocumentLink, DocumentVersion


def test_document_lifecycle_values_are_stable() -> None:
    assert [item.value for item in DocumentLifecycleStatus] == [
        "draft",
        "working",
        "final",
        "archived",
    ]


def test_document_version_has_unique_document_version_number() -> None:
    constraints = list(DocumentVersion.__table__.constraints)
    assert any(
        isinstance(item, UniqueConstraint)
        and tuple(column.name for column in item.columns) == ("document_id", "version_number")
        for item in constraints
    )


def test_document_link_declares_exactly_one_target_check() -> None:
    checks = [
        str(item.sqltext)
        for item in DocumentLink.__table__.constraints
        if isinstance(item, CheckConstraint)
    ]
    assert any("num_nonnulls" in sql and "= 1" in sql for sql in checks)


def test_document_has_optimistic_version_and_current_version_pointer() -> None:
    assert Document.__table__.c.version.nullable is False
    assert Document.__table__.c.current_version_id.nullable is True
