import uuid
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.documents import repository
from app.modules.documents.control import (
    DocumentSnapshot,
    RequirementSnapshot,
    classify_document,
)
from app.modules.documents.policy import DocumentUploadPolicyError
from app.modules.documents.repository import (
    document_tables_available,
    get_organization_document,
    list_active_requirements,
    list_organization_documents,
)
from app.modules.documents.schemas import (
    OrganizationDocumentListResponse,
    OrganizationDocumentResponse,
)
from app.modules.documents.service import DocumentNotFoundError, DocumentService
from app.modules.documents.targets import DocumentTarget
from app.modules.identity.authorization import AuthorizationContext, can_access_organization
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.opo.models import OPO
from app.modules.organizations.repository import get_organization
from app.storage.local import StorageLimitExceeded

router = APIRouter(
    prefix="/api/organizations/{organization_id}/documents",
    tags=["documents"],
)
service = DocumentService()

_dep_view = Depends(require_scoped_permission("documents.view"))  # noqa: B008
_dep_download = Depends(require_scoped_permission("documents.download"))  # noqa: B008
_dep_upload = Depends(require_scoped_permission("documents.upload"))  # noqa: B008
_dep_delete = Depends(require_scoped_permission("documents.delete"))  # noqa: B008


def _organization_or_404(
    db: Session,
    organization_id: uuid.UUID,
    authorization: AuthorizationContext,
):
    organization = get_organization(db, organization_id)
    if organization is None or not can_access_organization(authorization, organization):
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


def _require_document_tables(db: Session) -> None:
    if not document_tables_available(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Documents storage schema is not migrated",
        )


def _document_response(db: Session, organization_id: uuid.UUID, document):
    has_opo = db.scalar(
        select(OPO.id).where(
            OPO.deleted_at.is_(None),
            or_(
                OPO.owner_organization_id == organization_id,
                OPO.operating_organization_id == organization_id,
            ),
        )
    ) is not None
    matching_requirements = [
        row
        for row in list_active_requirements(db)
        if row.document_type == document.document_type
        and (row.applicability == "all" or (row.applicability == "has_opo" and has_opo))
    ]
    requirement = matching_requirements[0] if matching_requirements else None
    snapshot = (
        RequirementSnapshot(
            document_type=requirement.document_type,
            required=requirement.required,
            expiry_required=any(row.expiry_required for row in matching_requirements),
            applicability=requirement.applicability,
            active=requirement.active,
        )
        if requirement
        else None
    )
    payload = OrganizationDocumentResponse.model_validate(document).model_dump()
    payload["status"] = classify_document(
        DocumentSnapshot(document.document_type, document.expires_at), snapshot, date.today()
    ).value
    return payload


@router.get("", response_model=OrganizationDocumentListResponse)
def read_documents(
    organization_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    if not document_tables_available(db):
        return OrganizationDocumentListResponse(source_available=False, items=[])
    return OrganizationDocumentListResponse(
        source_available=True,
        items=[
            _document_response(db, organization_id, document)
            for document in list_organization_documents(db, organization_id)
        ],
    )


@router.post("", response_model=OrganizationDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    organization_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form(min_length=1, max_length=120)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    issued_at: Annotated[date | None, Form()] = None,
    expires_at: Annotated[date | None, Form()] = None,
    authorization: AuthorizationContext = _dep_upload,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    document_type = document_type.strip()
    title = title.strip()
    if not document_type or not title:
        raise HTTPException(status_code=422, detail="Document type and title are required")

    try:
        document = service.create_document(
            db,
            actor_user_id=authorization.user_id,
            target=DocumentTarget(organization_id=organization_id),
            document_type=document_type,
            title=title,
            original_filename=file.filename or "document",
            content_type=file.content_type,
            source=file.file,
            issued_at=issued_at,
            expires_at=expires_at,
        )
    except DocumentUploadPolicyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageLimitExceeded as exc:
        raise HTTPException(status_code=413, detail="Document exceeds 20 MiB limit") from exc
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is unavailable",
        ) from exc

    projection = get_organization_document(db, organization_id, document.id)
    if projection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document projection is unavailable",
        )
    return _document_response(db, organization_id, projection)


@router.get("/{document_id}/download")
def download_document(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_download,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    document = get_organization_document(db, organization_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        stream = service.open_document(document)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document file is unavailable",
        ) from exc
    return StreamingResponse(
        stream,
        media_type=document.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (
                "attachment; filename*=UTF-8''" + quote(document.original_filename)
            )
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_delete,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    projection = get_organization_document(db, organization_id, document_id)
    if projection is None:
        raise HTTPException(status_code=404, detail="Document not found")
    document = repository.get_document(db, projection.id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        service.soft_delete_document(
            db,
            actor_user_id=authorization.user_id,
            document=document,
            expected_version=None,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Document not found") from exc
    return None
