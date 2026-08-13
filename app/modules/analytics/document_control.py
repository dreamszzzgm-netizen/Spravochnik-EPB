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
class DocumentRecord:
    document_type: str
    expires_at: date | None = None
    expiry_required: bool = False


@dataclass(frozen=True, slots=True)
class DocumentRequirement:
    document_type: str
    required: bool = True


def classify_document(document: DocumentRecord, today: date) -> DocumentStatus:
    """Classify an uploaded document without mutating source domain data."""
    if document.expires_at is None:
        if document.expiry_required:
            return DocumentStatus.NO_EXPIRY
        return DocumentStatus.VALID

    days_left = (document.expires_at - today).days
    if days_left < 0:
        return DocumentStatus.EXPIRED
    if days_left <= 14:
        return DocumentStatus.EXPIRING_14
    if days_left <= 40:
        return DocumentStatus.EXPIRING_40
    return DocumentStatus.VALID


def missing_requirements(
    requirements: list[DocumentRequirement],
    uploaded: list[DocumentRecord],
) -> list[DocumentRequirement]:
    """Return explicitly required document types that have no uploaded record."""
    uploaded_types = {document.document_type for document in uploaded}
    return [
        requirement
        for requirement in requirements
        if requirement.required and requirement.document_type not in uploaded_types
    ]
