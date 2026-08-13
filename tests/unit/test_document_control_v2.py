from datetime import date

from app.modules.documents.control import (
    DocumentSnapshot,
    DocumentStatus,
    RequirementSnapshot,
    classify_document,
    missing_requirements,
)


def test_document_expiration_boundaries() -> None:
    today = date(2026, 8, 13)
    requirement = RequirementSnapshot("insurance", True, True)
    cases = [
        (date(2026, 8, 12), DocumentStatus.EXPIRED),
        (date(2026, 8, 27), DocumentStatus.EXPIRING_14),
        (date(2026, 8, 28), DocumentStatus.EXPIRING_40),
        (date(2026, 9, 22), DocumentStatus.EXPIRING_40),
        (date(2026, 9, 23), DocumentStatus.VALID),
    ]
    for expires_at, expected in cases:
        assert classify_document(
            DocumentSnapshot("insurance", expires_at), requirement, today
        ) is expected


def test_required_expiry_without_date_is_distinct() -> None:
    requirement = RequirementSnapshot("insurance", True, True)
    assert classify_document(
        DocumentSnapshot("insurance", None), requirement, date(2026, 8, 13)
    ) is DocumentStatus.NO_EXPIRY


def test_missing_comes_only_from_applicable_requirements() -> None:
    requirements = [
        RequirementSnapshot("company_card", True, False, "all"),
        RequirementSnapshot("opo_certificate", True, False, "has_opo"),
        RequirementSnapshot("optional", False, False, "all"),
    ]
    documents = [DocumentSnapshot("company_card", None)]

    assert missing_requirements(requirements, documents, has_opo=False) == []
    assert [item.document_type for item in missing_requirements(
        requirements, documents, has_opo=True
    )] == ["opo_certificate"]
