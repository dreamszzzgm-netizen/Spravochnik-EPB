import uuid
from datetime import date
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.documents.repository import (
    document_tables_available,
    get_organization_document,
    list_organization_documents,
)
from app.modules.documents.schemas import (
    OrganizationDocumentListResponse,
    OrganizationDocumentResponse,
)
from app.modules.documents.service import DocumentService
from app.modules.identity.authorization import AuthorizationContext, can_access_organization
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.organizations.repository import get_organization

router = APIRouter(
    prefix="/api/organizations/{organization_id}/documents",
    tags=["documents"],
)
service = DocumentService()

_dep_view = Depends(require_scoped_permission("organizations.view"))  # noqa: B008
_dep_update = Depends(require_scoped_permission("organizations.update"))  # noqa: B008
_MAX_DOCUMENT_BYTES = 20 * 1024 * 1024


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
        items=list_organization_documents(db, organization_id),
    )


@router.post("", response_model=OrganizationDocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    organization_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form(min_length=1, max_length=120)],
    title: Annotated[str, Form(min_length=1, max_length=255)],
    issued_at: Annotated[date | None, Form()] = None,
    expires_at: Annotated[date | None, Form()] = None,
    authorization: AuthorizationContext = _dep_update,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    if file.size is not None and file.size > _MAX_DOCUMENT_BYTES:
        raise HTTPException(status_code=413, detail="Document exceeds 20 MiB limit")
    document = service.create_document(
        db,
        organization_id=organization_id,
        document_type=document_type,
        title=title,
        original_filename=file.filename or "document",
        content_type=file.content_type,
        source=file.file,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    if document.size_bytes > _MAX_DOCUMENT_BYTES:
        service.storage.delete(document.storage_key)
        db.delete(document)
        db.commit()
        raise HTTPException(status_code=413, detail="Document exceeds 20 MiB limit")
    return document


@router.get("/{document_id}/download")
def download_document(
    organization_id: uuid.UUID,
    document_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_view,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    document = get_organization_document(db, organization_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return StreamingResponse(
        service.open_document(document),
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
    authorization: AuthorizationContext = _dep_update,
    db: Session = Depends(get_db),
):
    _organization_or_404(db, organization_id, authorization)
    _require_document_tables(db)
    document = get_organization_document(db, organization_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    service.soft_delete_document(db, document)
    return None
