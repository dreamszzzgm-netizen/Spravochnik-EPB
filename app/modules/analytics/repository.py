from collections import defaultdict
from datetime import date

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.modules.analytics.management import (
    DocumentControlSummary,
    DocumentIssue,
    ManagementInput,
    TaskSnapshot,
)
from app.modules.contracts.models import Contract
from app.modules.documents.control import (
    DocumentSnapshot,
    DocumentStatus,
    RequirementSnapshot,
    applicable_requirements,
    classify_document,
    missing_requirements,
)
from app.modules.documents.models import Document, DocumentLink, DocumentRequirement
from app.modules.opo.models import OPO
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task

_DOCUMENT_TABLES = {"documents", "document_versions", "document_links", "document_requirements"}


def _document_tables_available(db: Session) -> bool:
    schema = inspect(db.get_bind())
    return all(schema.has_table(table) for table in _DOCUMENT_TABLES)


def _organization_name(legal_name: str, short_name: str | None) -> str:
    return short_name or legal_name


def load_document_control(db: Session, *, today: date) -> DocumentControlSummary:
    if not _document_tables_available(db):
        return DocumentControlSummary(source_available=False)

    organization_rows = db.execute(
        select(Organization.id, Organization.legal_name, Organization.short_name).where(
            Organization.deleted_at.is_(None)
        )
    ).all()
    document_rows = list(
        db.execute(
            select(Document, DocumentLink.organization_id)
            .join(DocumentLink, DocumentLink.document_id == Document.id)
            .join(Organization, Organization.id == DocumentLink.organization_id)
            .where(
                Document.deleted_at.is_(None),
                DocumentLink.organization_id.is_not(None),
                Organization.deleted_at.is_(None),
            )
        ).all()
    )
    requirement_rows = list(
        db.scalars(
            select(DocumentRequirement).where(
                DocumentRequirement.active.is_(True),
                DocumentRequirement.required.is_(True),
            )
        ).all()
    )
    opo_rows = db.execute(
        select(OPO.owner_organization_id, OPO.operating_organization_id).where(
            OPO.deleted_at.is_(None)
        )
    ).all()
    opo_organizations = {value for row in opo_rows for value in row}

    documents_by_organization: dict[object, list[Document]] = defaultdict(list)
    for document, organization_id in document_rows:
        documents_by_organization[organization_id].append(document)

    requirements = [
        RequirementSnapshot(
            document_type=requirement.document_type,
            required=requirement.required,
            expiry_required=requirement.expiry_required,
            applicability=requirement.applicability,
        )
        for requirement in requirement_rows
    ]
    requirement_titles = {
        (requirement.document_type, requirement.applicability): requirement.title
        for requirement in requirement_rows
    }

    issues: list[DocumentIssue] = []
    counts = {status: 0 for status in DocumentStatus}

    for organization_id, legal_name, short_name in organization_rows:
        organization_name = _organization_name(legal_name, short_name)
        has_opo = organization_id in opo_organizations
        organization_documents = documents_by_organization.get(organization_id, [])
        snapshots = [
            DocumentSnapshot(document.document_type, document.expires_at)
            for document in organization_documents
        ]
        applicable = applicable_requirements(requirements, has_opo=has_opo)
        requirements_by_type: dict[str, list[RequirementSnapshot]] = defaultdict(list)
        for requirement in applicable:
            requirements_by_type[requirement.document_type].append(requirement)

        for document in organization_documents:
            matching = requirements_by_type.get(document.document_type, [])
            requirement = None
            if matching:
                requirement = RequirementSnapshot(
                    document_type=document.document_type,
                    required=True,
                    expiry_required=any(item.expiry_required for item in matching),
                )
            status_value = classify_document(
                DocumentSnapshot(document.document_type, document.expires_at),
                requirement,
                today,
            )
            counts[status_value] += 1
            if status_value in {
                DocumentStatus.EXPIRED,
                DocumentStatus.EXPIRING_14,
                DocumentStatus.EXPIRING_40,
                DocumentStatus.NO_EXPIRY,
            }:
                days_left = (
                    (document.expires_at - today).days
                    if document.expires_at is not None
                    else None
                )
                issues.append(
                    DocumentIssue(
                        organization_id=organization_id,
                        organization_name=organization_name,
                        document_type=document.document_type,
                        document_title=document.title,
                        status=status_value,
                        expires_at=document.expires_at,
                        days_left=days_left,
                    )
                )

        for requirement in missing_requirements(
            requirements,
            snapshots,
            has_opo=has_opo,
        ):
            counts[DocumentStatus.MISSING] += 1
            title = requirement_titles.get(
                (requirement.document_type, requirement.applicability),
                requirement.document_type,
            )
            issues.append(
                DocumentIssue(
                    organization_id=organization_id,
                    organization_name=organization_name,
                    document_type=requirement.document_type,
                    document_title=title,
                    status=DocumentStatus.MISSING,
                )
            )

    priority = {
        DocumentStatus.EXPIRED: 0,
        DocumentStatus.MISSING: 1,
        DocumentStatus.NO_EXPIRY: 2,
        DocumentStatus.EXPIRING_14: 3,
        DocumentStatus.EXPIRING_40: 4,
    }
    issues.sort(
        key=lambda item: (
            priority.get(item.status, 99),
            item.days_left if item.days_left is not None else 10_000,
            item.organization_name.casefold(),
            item.document_title.casefold(),
        )
    )

    return DocumentControlSummary(
        source_available=True,
        total=len(document_rows),
        expired=counts[DocumentStatus.EXPIRED],
        expiring_14=counts[DocumentStatus.EXPIRING_14],
        expiring_40=counts[DocumentStatus.EXPIRING_40],
        missing=counts[DocumentStatus.MISSING],
        no_expiry=counts[DocumentStatus.NO_EXPIRY],
        valid=counts[DocumentStatus.VALID],
        issues=tuple(issues),
    )


def load_management_input(db: Session, *, today: date) -> ManagementInput:
    organizations_total = db.scalar(
        select(func.count()).select_from(Organization).where(Organization.deleted_at.is_(None))
    ) or 0
    contract_statuses = list(
        db.scalars(select(Contract.status).where(Contract.deleted_at.is_(None))).all()
    )
    task_rows = db.execute(
        select(Task.status, Task.due_date).where(Task.deleted_at.is_(None))
    ).all()
    return ManagementInput(
        organizations_total=organizations_total,
        contract_statuses=contract_statuses,
        tasks=[TaskSnapshot(status=status, due_date=due_date) for status, due_date in task_rows],
        documents=load_document_control(db, today=today),
    )
