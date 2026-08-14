"""Import service: normalization, validation, matching, confirmation."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.import_.enums import CandidateAction, CandidateStatus, ImportSessionStatus
from app.modules.import_.models import ImportCandidate, ImportSession
from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.models import Organization
from app.modules.organizations.repository import find_identifier_by_type_and_value
from app.modules.organizations.service import (
    OrganizationLegalFormError,
    OrganizationService,
    OrganizationValidationError,
    validate_organization_legal_form,
    validate_parent_for_organization,
)


class ImportSessionNotFoundError(Exception):
    pass


class ImportSessionConflictError(Exception):
    pass


class ImportError(Exception):
    pass


_ORG_TYPE_MAP = {
    "юрлицо": OrganizationType.LEGAL_ENTITY,
    "юридическое лицо": OrganizationType.LEGAL_ENTITY,
    "юр. лицо": OrganizationType.LEGAL_ENTITY,
    "legal_entity": OrganizationType.LEGAL_ENTITY,
    "ооо": OrganizationType.LEGAL_ENTITY,
    "зао": OrganizationType.LEGAL_ENTITY,
    "оао": OrganizationType.LEGAL_ENTITY,
    "пп": OrganizationType.LEGAL_ENTITY,
    "ао": OrganizationType.LEGAL_ENTITY,
    "ип": OrganizationType.INDIVIDUAL_ENTREPRENEUR,
    "индивидуальный предприниматель": OrganizationType.INDIVIDUAL_ENTREPRENEUR,
    "individual_entrepreneur": OrganizationType.INDIVIDUAL_ENTREPRENEUR,
    "филиал": OrganizationType.BRANCH,
    "подразделение": OrganizationType.BRANCH,
    "branch": OrganizationType.BRANCH,
}


def _parse_organization_type(raw: str | None) -> OrganizationType | None:
    if not raw:
        return None
    key = raw.strip().lower()
    return _ORG_TYPE_MAP.get(key)


def normalize_candidate_data(data: dict[str, str | None]) -> dict:
    """Normalize raw row data into structured candidate data."""
    org_type = _parse_organization_type(data.get("organization_type"))

    inn = data.get("inn", "").strip() if data.get("inn") else None
    kpp = data.get("kpp", "").strip() if data.get("kpp") else None
    ogrn = data.get("ogrn", "").strip() if data.get("ogrn") else None
    ogrnip = data.get("ogrnip", "").strip() if data.get("ogrnip") else None

    if inn and not org_type:
        if len(inn) == 12:
            org_type = OrganizationType.INDIVIDUAL_ENTREPRENEUR
        elif len(inn) == 10:
            org_type = OrganizationType.LEGAL_ENTITY

    return {
        "organization_type": org_type,
        "legal_name": data.get("legal_name"),
        "short_name": data.get("short_name"),
        "inn": inn,
        "kpp": kpp,
        "ogrn": ogrn,
        "ogrnip": ogrnip,
        "legal_address": data.get("legal_address"),
        "actual_address": data.get("actual_address"),
        "residence_address": data.get("residence_address"),
        "director_name": data.get("director_name"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "bank_details": data.get("bank_details"),
        "parent_inn": data.get("parent_inn"),
        "parent_kpp": data.get("parent_kpp"),
    }


def validate_candidate(data: dict) -> list[str]:
    """Validate a normalized candidate, returning error messages."""
    errors: list[str] = []
    org_type = data.get("organization_type")

    if org_type is None:
        errors.append("Не удалось определить тип организации")
        return errors

    legal_name = data.get("legal_name")
    if not legal_name or not legal_name.strip():
        errors.append("Наименование организации обязательно")

    inn = data.get("inn")
    if inn:
        if org_type == OrganizationType.INDIVIDUAL_ENTREPRENEUR and len(inn) not in (10, 12):
            errors.append(f"ИНН для ИП должен содержать 10 или 12 цифр (получено {len(inn)})")
        elif org_type == OrganizationType.LEGAL_ENTITY and len(inn) != 10:
            errors.append(
                f"ИНН для юрлица должен содержать 10 цифр (получено {len(inn)})"
            )
        elif org_type == OrganizationType.BRANCH and len(inn) not in (10, 12):
            errors.append(f"ИНН должен содержать 10 или 12 цифр (получено {len(inn)})")

    if org_type == OrganizationType.LEGAL_ENTITY:
        if not inn:
            errors.append("ИНН обязателен для юридического лица")
        ogrn = data.get("ogrn")
        if ogrn and len(ogrn) != 13:
            errors.append(f"ОГРН должен содержать 13 цифр (получено {len(ogrn)})")
    elif org_type == OrganizationType.INDIVIDUAL_ENTREPRENEUR:
        if not inn:
            errors.append("ИНН обязателен для ИП")
        ogrnip = data.get("ogrnip")
        if ogrnip and len(ogrnip) != 15:
            errors.append(f"ОГРНИП должен содержать 15 цифр (получено {len(ogrnip)})")
    elif org_type == OrganizationType.BRANCH:
        parent_inn = data.get("parent_inn")
        if not parent_inn:
            errors.append("ИНН головной организации обязателен для филиала")

    return errors


def match_organization(
    db: Session,
    data: dict,
) -> tuple[Organization | None, str]:
    """Find a matching existing organization using deterministic identifiers.

    Returns (organization, match_type) where match_type is:
    - "exact_ogrnip": OGRNIP match (IP only)
    - "exact_inn": INN match (LE/BRANCH)
    - "exact_inn_kpp": INN+KPP match (LE/BRANCH)
    - "name_match": name-only match (potential duplicate)
    - "": no match
    """
    org_type = data.get("organization_type")
    inn = data.get("inn")
    kpp = data.get("kpp")
    ogrnip = data.get("ogrnip")

    if org_type == OrganizationType.INDIVIDUAL_ENTREPRENEUR:
        if ogrnip:
            existing_id = find_identifier_by_type_and_value(
                db, identifier_type=IdentifierType.OGRNIP, identifier_value=ogrnip
            )
            if existing_id:
                org = db.get(Organization, existing_id.organization_id)
                if org and org.deleted_at is None:
                    return org, "exact_ogrnip"
        if inn:
            existing_id = find_identifier_by_type_and_value(
                db, identifier_type=IdentifierType.INN, identifier_value=inn
            )
            if existing_id:
                org = db.get(Organization, existing_id.organization_id)
                if org and org.deleted_at is None:
                    return org, "exact_inn"

    elif org_type == OrganizationType.BRANCH or org_type == OrganizationType.LEGAL_ENTITY:
        if inn and kpp:
            inn_id = find_identifier_by_type_and_value(
                db, identifier_type=IdentifierType.INN, identifier_value=inn
            )
            if inn_id:
                kpp_id = find_identifier_by_type_and_value(
                    db, identifier_type=IdentifierType.KPP, identifier_value=kpp
                )
                if kpp_id and inn_id.organization_id == kpp_id.organization_id:
                    org = db.get(Organization, inn_id.organization_id)
                    if org and org.deleted_at is None:
                        return org, "exact_inn_kpp"
        if inn:
            existing_id = find_identifier_by_type_and_value(
                db, identifier_type=IdentifierType.INN, identifier_value=inn
            )
            if existing_id:
                org = db.get(Organization, existing_id.organization_id)
                if org and org.deleted_at is None:
                    return org, "exact_inn"

    legal_name = data.get("legal_name")
    if legal_name:
        stmt = select(Organization).where(
            Organization.legal_name.ilike(f"%{legal_name.strip()}%"),
            Organization.deleted_at.is_(None),
        )
        org = db.scalars(stmt).first()
        if org:
            return org, "name_match"

    return None, ""


def _determine_status_and_action(
    match_org: Organization | None,
    match_type: str,
    errors: list[str],
) -> tuple[CandidateStatus, CandidateAction]:
    """Determine candidate status and proposed action.

    Deterministic matches (exact_inn, exact_inn_kpp, exact_ogrnip) → UPDATE.
    Name-only match → POTENTIAL_DUPLICATE (user decides).
    No match → CREATE.
    Errors → ERROR.
    """
    if errors:
        return CandidateStatus.ERROR, CandidateAction.SKIP

    if match_org:
        if match_type in ("exact_inn", "exact_inn_kpp", "exact_ogrnip"):
            return CandidateStatus.UPDATE, CandidateAction.UPDATE
        return CandidateStatus.POTENTIAL_DUPLICATE, CandidateAction.SKIP

    return CandidateStatus.NEW, CandidateAction.CREATE


def check_ogrn_uniqueness(
    db: Session, data: dict, exclude_org_id: uuid.UUID | None = None
) -> str | None:
    """Check OGRN/OGRNIP uniqueness. Returns error message if duplicate found."""
    ogrn = data.get("ogrn")
    if ogrn:
        existing = find_identifier_by_type_and_value(
            db, identifier_type=IdentifierType.OGRN, identifier_value=ogrn
        )
        if existing and (exclude_org_id is None or existing.organization_id != exclude_org_id):
            org = db.get(Organization, existing.organization_id)
            name = org.legal_name if org else "unknown"
            return f"ОГРН {ogrn} уже используется организацией: {name}"

    ogrnip = data.get("ogrnip")
    if ogrnip:
        existing = find_identifier_by_type_and_value(
            db, identifier_type=IdentifierType.OGRNIP, identifier_value=ogrnip
        )
        if existing and (exclude_org_id is None or existing.organization_id != exclude_org_id):
            org = db.get(Organization, existing.organization_id)
            name = org.legal_name if org else "unknown"
            return f"ОГРНИП {ogrnip} уже используется организацией: {name}"

    return None


def process_candidate(
    db: Session,
    session_id: uuid.UUID,
    row_number: int,
    raw_data: dict[str, str | None],
) -> ImportCandidate:
    """Process a single row: normalize, validate, match."""
    normalized = normalize_candidate_data(raw_data)
    errors = validate_candidate(normalized)

    match_org, match_type = match_organization(db, normalized)
    ogrn_error = check_ogrn_uniqueness(db, normalized)
    if ogrn_error:
        errors.append(ogrn_error)

    status, action = _determine_status_and_action(match_org, match_type, errors)

    warnings: list[str] = []
    if match_type == "name_match" and match_org:
        warnings.append(f"Найдена похожая организация: {match_org.legal_name}")

    candidate = ImportCandidate(
        session_id=session_id,
        row_number=row_number,
        raw_data=raw_data,
        normalized_data=normalized,
        validation_errors=errors if errors else None,
        warnings=warnings if warnings else None,
        candidate_status=status,
        proposed_action=action,
        matched_organization_id=match_org.id if match_org else None,
    )
    db.add(candidate)
    return candidate


def create_import_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    filename: str | None = None,
    source: str = "excel",
) -> ImportSession:
    """Create a new import session."""
    session = ImportSession(
        user_id=user_id,
        filename=filename,
        source=source,
        status=ImportSessionStatus.UPLOADED,
    )
    db.add(session)
    db.flush()
    write_audit(
        db,
        action="import.session_created",
        summary="Import session created",
        result="success",
        user_id=user_id,
        entity_type="import_session",
        entity_id=session.id,
        metadata={"filename": filename, "source": source},
    )
    db.commit()
    db.refresh(session)
    return session


def update_session_counts(db: Session, session: ImportSession) -> None:
    """Recompute session counts from candidates."""
    candidates = list(
        db.scalars(
            select(ImportCandidate).where(ImportCandidate.session_id == session.id)
        )
    )
    session.candidate_count = len(candidates)
    session.added_count = sum(
        1 for c in candidates if c.candidate_status == CandidateStatus.NEW
    )
    session.updated_count = sum(
        1 for c in candidates if c.candidate_status == CandidateStatus.UPDATE
    )
    session.duplicate_count = sum(
        1 for c in candidates if c.candidate_status == CandidateStatus.POTENTIAL_DUPLICATE
    )
    session.conflict_count = sum(
        1 for c in candidates if c.candidate_status == CandidateStatus.CONFLICT
    )
    session.error_count = sum(
        1 for c in candidates if c.candidate_status == CandidateStatus.ERROR
    )
    session.skipped_count = sum(
        1 for c in candidates if c.proposed_action == CandidateAction.SKIP
    )


def confirm_import_session(
    db: Session,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ImportSession:
    """Confirm and apply an import session transactionally.

    Creates new organizations and updates matched ones.
    Idempotent: completed sessions return existing results.
    """
    session = db.get(ImportSession, session_id)
    if session is None:
        raise ImportSessionNotFoundError("Import session not found")

    if session.status == ImportSessionStatus.COMPLETED:
        return session

    if session.status not in (ImportSessionStatus.PREVIEW_READY, ImportSessionStatus.CONFIRMED):
        raise ImportSessionConflictError(
            f"Session cannot be confirmed in status '{session.status.value}'"
        )

    if session.user_id != user_id:
        raise ImportSessionConflictError("Session does not belong to current user")

    session.status = ImportSessionStatus.APPLYING
    db.flush()

    org_service = OrganizationService()
    candidates = list(
        db.scalars(
            select(ImportCandidate)
            .where(ImportCandidate.session_id == session_id)
            .order_by(ImportCandidate.row_number)
        )
    )

    created_ids: list[str] = []
    updated_ids: list[str] = []

    try:
        for candidate in candidates:
            if candidate.proposed_action == CandidateAction.SKIP:
                continue

            if candidate.proposed_action == CandidateAction.CREATE:
                data = candidate.normalized_data or {}
                org_type = data.get("organization_type")
                if org_type is None:
                    continue

                identifiers = _build_identifiers_list(data)

                try:
                    validate_organization_legal_form(
                        org_type,
                        legal_address=data.get("legal_address"),
                        actual_address=data.get("actual_address"),
                        director_name=data.get("director_name"),
                        residence_address=data.get("residence_address"),
                        passport_details=None,
                        identifiers=identifiers,
                    )
                    validate_parent_for_organization(
                        db,
                        organization_type=org_type,
                        parent_id=None,
                    )
                except (OrganizationLegalFormError, OrganizationValidationError) as exc:
                    candidate.candidate_status = CandidateStatus.ERROR
                    candidate.validation_errors = [str(exc)]
                    candidate.proposed_action = CandidateAction.SKIP
                    session.error_count += 1
                    continue

                org = org_service.create_organization(
                    db,
                    actor_id=user_id,
                    legal_name=data.get("legal_name", ""),
                    short_name=data.get("short_name"),
                    organization_type=org_type,
                    parent_id=None,
                    legal_address=data.get("legal_address"),
                    actual_address=data.get("actual_address"),
                    residence_address=data.get("residence_address"),
                    director_name=data.get("director_name"),
                    phone=data.get("phone"),
                    email=data.get("email"),
                    bank_details=data.get("bank_details"),
                    identifiers=identifiers,
                )
                created_ids.append(str(org.id))
                session.added_count += 1

            elif candidate.proposed_action == CandidateAction.UPDATE:
                if candidate.matched_organization_id is None:
                    continue
                org = db.get(Organization, candidate.matched_organization_id)
                if org is None or org.deleted_at is not None:
                    candidate.candidate_status = CandidateStatus.ERROR
                    candidate.validation_errors = ["Организация не найдена или удалена"]
                    continue

                data = candidate.normalized_data or {}
                identifiers = _build_identifiers_list(data)

                try:
                    org_service.update_organization(
                        db,
                        actor_id=user_id,
                        organization=org,
                        legal_name=data.get("legal_name"),
                        short_name=data.get("short_name"),
                        organization_type=data.get("organization_type"),
                        parent_id=None,
                        legal_address=data.get("legal_address"),
                        actual_address=data.get("actual_address"),
                        residence_address=data.get("residence_address"),
                        director_name=data.get("director_name"),
                        phone=data.get("phone"),
                        email=data.get("email"),
                        bank_details=data.get("bank_details"),
                        identifiers=identifiers,
                    )
                except Exception as exc:
                    candidate.candidate_status = CandidateStatus.ERROR
                    candidate.validation_errors = [str(exc)]
                    continue

                updated_ids.append(str(org.id))
                session.updated_count += 1

        session.status = ImportSessionStatus.COMPLETED
        session.result_summary = {
            "created": created_ids,
            "updated": updated_ids,
        }
        write_audit(
            db,
            action="import.session_confirmed",
            summary="Import session confirmed and applied",
            result="success",
            user_id=user_id,
            entity_type="import_session",
            entity_id=session.id,
            metadata={
                "created_count": len(created_ids),
                "updated_count": len(updated_ids),
            },
        )
        db.commit()
        db.refresh(session)

    except Exception:
        session.status = ImportSessionStatus.FAILED
        db.commit()
        raise

    return session


def _build_identifiers_list(data: dict) -> list[dict]:
    """Build identifiers list from normalized data."""
    identifiers = []
    inn = data.get("inn")
    if inn:
        identifiers.append({
            "identifier_type": IdentifierType.INN,
            "identifier_value": inn,
            "is_primary": True,
        })
    kpp = data.get("kpp")
    if kpp:
        identifiers.append({
            "identifier_type": IdentifierType.KPP,
            "identifier_value": kpp,
            "is_primary": False,
        })
    ogrn = data.get("ogrn")
    if ogrn:
        identifiers.append({
            "identifier_type": IdentifierType.OGRN,
            "identifier_value": ogrn,
            "is_primary": False,
        })
    ogrnip = data.get("ogrnip")
    if ogrnip:
        identifiers.append({
            "identifier_type": IdentifierType.OGRNIP,
            "identifier_value": ogrnip,
            "is_primary": True,
        })
    return identifiers
