from datetime import date

from app.modules.analytics.document_control import (
    DocumentRecord,
    DocumentRequirement,
    DocumentStatus,
    classify_document,
    missing_requirements,
)


def test_classifies_document_expiration_boundaries() -> None:
    today = date(2026, 8, 13)

    cases = [
        (date(2026, 8, 12), DocumentStatus.EXPIRED),
        (date(2026, 8, 13), DocumentStatus.EXPIRING_14),
        (date(2026, 8, 27), DocumentStatus.EXPIRING_14),
        (date(2026, 8, 28), DocumentStatus.EXPIRING_40),
        (date(2026, 9, 22), DocumentStatus.EXPIRING_40),
        (date(2026, 9, 23), DocumentStatus.VALID),
    ]

    for expires_at, expected in cases:
        document = DocumentRecord("insurance", expires_at)
        assert classify_document(document, today) is expected


def test_document_without_expiry_is_distinguished_when_expiry_is_required() -> None:
    today = date(2026, 8, 13)
    document = DocumentRecord("insurance", None, expiry_required=True)

    assert classify_document(document, today) is DocumentStatus.NO_EXPIRY


def test_missing_documents_come_from_requirements_not_guessed_absence() -> None:
    requirements = [
        DocumentRequirement("company_card", required=True),
        DocumentRequirement("insurance", required=True),
        DocumentRequirement("optional_other", required=False),
    ]
    uploaded = [DocumentRecord("company_card", None)]

    missing = missing_requirements(requirements, uploaded)

    assert [item.document_type for item in missing] == ["insurance"]
