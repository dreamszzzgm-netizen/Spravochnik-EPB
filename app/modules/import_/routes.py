import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.import_.enums import CandidateAction, ImportSessionStatus
from app.modules.import_.excel_parser import parse_xlsx_batch
from app.modules.import_.models import ImportCandidate, ImportSession
from app.modules.import_.schemas import (
    ImportCandidateResponse,
    ImportCandidateUpdateRequest,
    ImportReportResponse,
    ImportSessionListResponse,
    ImportSessionResponse,
)
from app.modules.import_.service import (
    ImportSessionConflictError,
    ImportSessionNotFoundError,
    confirm_import_session,
    create_import_session,
    process_candidate,
    update_session_counts,
    validate_candidate,
)

router = APIRouter(prefix="/api/import", tags=["import"])

_dep_import = Depends(require_scoped_permission("organizations.import"))  # noqa: B008


def _get_session_or_404(db: Session, session_id: uuid.UUID) -> ImportSession:
    session = db.get(ImportSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Import session not found")
    return session


@router.post("/sessions", response_model=ImportSessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = create_import_session(db, user_id=authorization.user_id)
    return session


@router.post(
    "/sessions/{session_id}/upload-excel",
    response_model=ImportSessionResponse,
)
async def upload_excel(
    session_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)

    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status not in (ImportSessionStatus.UPLOADED, ImportSessionStatus.PROCESSING):
        raise HTTPException(
            status_code=409,
            detail=f"Session cannot accept uploads in status '{session.status.value}'",
        )

    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Only .xlsx files are supported")

    raw = await file.read(10 * 1024 * 1024 + 1)
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    session.status = ImportSessionStatus.PROCESSING
    session.filename = file.filename
    db.flush()

    try:
        unmapped_headers, rows = parse_xlsx_batch(raw)
    except ImportError as exc:
        raise HTTPException(status_code=500, detail="openpyxl is not installed") from exc
    except Exception as exc:
        session.status = ImportSessionStatus.FAILED
        db.commit()
        raise HTTPException(
            status_code=422, detail=f"Failed to parse Excel: {exc}"
        ) from exc

    if not rows:
        session.status = ImportSessionStatus.FAILED
        db.commit()
        raise HTTPException(status_code=422, detail="No data rows found in Excel file")

    if unmapped_headers:
        for row in rows:
            row.errors.append(f"Неизвестные колонки: {', '.join(unmapped_headers)}")

    for row in rows:
        process_candidate(db, session.id, row.row_number, row.raw_data)

    update_session_counts(db, session)

    has_errors = any(
        c.validation_errors for c in db.scalars(
            select(ImportCandidate).where(ImportCandidate.session_id == session.id)
        )
    )

    session.status = (
        ImportSessionStatus.FAILED if has_errors and session.error_count == session.candidate_count
        else ImportSessionStatus.PREVIEW_READY
    )
    db.commit()
    db.refresh(session)
    return session


@router.get(
    "/sessions",
    response_model=ImportSessionListResponse,
)
def list_sessions(
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    stmt = (
        select(ImportSession)
        .where(ImportSession.user_id == authorization.user_id)
        .order_by(ImportSession.created_at.desc())
        .limit(50)
    )
    sessions = list(db.scalars(stmt))
    return ImportSessionListResponse(items=sessions, total=len(sessions))


@router.get(
    "/sessions/{session_id}",
    response_model=ImportSessionResponse,
)
def get_session(
    session_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=404, detail="Import session not found")
    return session


@router.get(
    "/sessions/{session_id}/candidates",
    response_model=list[ImportCandidateResponse],
)
def list_candidates(
    session_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=404, detail="Import session not found")

    candidates = list(
        db.scalars(
            select(ImportCandidate)
            .where(ImportCandidate.session_id == session_id)
            .order_by(ImportCandidate.row_number)
        )
    )
    return candidates


@router.patch(
    "/sessions/{session_id}/candidates/{candidate_id}",
    response_model=ImportCandidateResponse,
)
def update_candidate(
    session_id: uuid.UUID,
    candidate_id: uuid.UUID,
    payload: ImportCandidateUpdateRequest,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status not in (ImportSessionStatus.PREVIEW_READY, ImportSessionStatus.CONFIRMED):
        raise HTTPException(
            status_code=409,
            detail=f"Session cannot be modified in status '{session.status.value}'",
        )

    candidate = db.get(ImportCandidate, candidate_id)
    if candidate is None or candidate.session_id != session_id:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.proposed_action = payload.proposed_action

    if payload.normalized_data:
        candidate.normalized_data = payload.normalized_data.model_dump(exclude_none=True)
        errors = validate_candidate(candidate.normalized_data)
        candidate.validation_errors = errors if errors else None

    if payload.proposed_action == CandidateAction.SKIP:
        candidate.candidate_status = candidate.candidate_status  # keep current status

    update_session_counts(db, session)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.post(
    "/sessions/{session_id}/confirm",
    response_model=ImportSessionResponse,
)
def confirm_session(
    session_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    try:
        session = confirm_import_session(
            db, session_id=session_id, user_id=authorization.user_id
        )
    except ImportSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportSessionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return session


@router.get(
    "/sessions/{session_id}/report",
    response_model=ImportReportResponse,
)
def get_report(
    session_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=404, detail="Import session not found")

    candidates = list(
        db.scalars(
            select(ImportCandidate)
            .where(ImportCandidate.session_id == session_id)
            .order_by(ImportCandidate.row_number)
        )
    )
    return ImportReportResponse(session=session, candidates=candidates)


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=ImportSessionResponse,
)
def cancel_session(
    session_id: uuid.UUID,
    authorization: AuthorizationContext = _dep_import,
    db: Session = Depends(get_db),
):
    session = _get_session_or_404(db, session_id)
    if session.user_id != authorization.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if session.status in (ImportSessionStatus.COMPLETED, ImportSessionStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Session cannot be cancelled in status '{session.status.value}'",
        )

    session.status = ImportSessionStatus.CANCELLED
    db.commit()
    db.refresh(session)
    return session
