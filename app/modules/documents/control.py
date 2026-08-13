import enum
from dataclasses import dataclass
from datetime import date


class DocumentStatus(enum.StrEnum):
    EXPIRED = "expired"
    EXPIRING_14 = "expiring_14"
    EXPIRING_40 = "expiring_40"
    VALID = "valid"
    MISSING = "missing"
    NO_EXPIRY = "no_expiry"


@dataclass(frozen=True, slots=True)
class DocumentSnapshot:
    document_type: str
    expires_at: date | None


@dataclass(frozen=True, slots=True)
class RequirementSnapshot:
    document_type: str
    required: bool
    expiry_required: bool
    applicability: str = "all"


def classify_document(
    document: DocumentSnapshot,
    requirement: RequirementSnapshot | None,
    today: date,
) -> DocumentStatus:
    expiry_required = requirement.expiry_required if requirement else False
    if document.expires_at is None:
        return DocumentStatus.NO_EXPIRY if expiry_required else DocumentStatus.VALID
    days_left = (document.expires_at - today).days
    if days_left < 0:
        return DocumentStatus.EXPIRED
    if days_left <= 14:
        return DocumentStatus.EXPIRING_14
    if days_left <= 40:
        return DocumentStatus.EXPIRING_40
    return DocumentStatus.VALID


def applicable_requirements(
    requirements: list[RequirementSnapshot], *, has_opo: bool
) -> list[RequirementSnapshot]:
    return [
        requirement
        for requirement in requirements
        if requirement.required
        and (
            requirement.applicability == "all"
            or (requirement.applicability == "has_opo" and has_opo)
        )
    ]


def missing_requirements(
    requirements: list[RequirementSnapshot],
    documents: list[DocumentSnapshot],
    *,
    has_opo: bool,
) -> list[RequirementSnapshot]:
    uploaded = {document.document_type for document in documents}
    return [
        requirement
        for requirement in applicable_requirements(requirements, has_opo=has_opo)
        if requirement.document_type not in uploaded
    ]
