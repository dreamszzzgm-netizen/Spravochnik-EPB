import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.buildings.repository import get_building
from app.modules.contracts import repository
from app.modules.contracts.models import Contract
from app.modules.contracts.schemas import (
    ContractCreate,
    ContractItemCreate,
    ContractItemResponse,
    ContractPaginatedResponse,
    ContractResponse,
    ContractResponsiblesReplace,
    ContractResponsiblesResponse,
    ExpertiseTypeResponse,
)
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
    can_access_building,
    can_access_technical_device,
    can_reference_organizations,
)
from app.modules.identity.dependencies import require_scoped_permission
from app.modules.identity.models import User
from app.modules.identity.repository import get_active_permission_scope_grants
from app.modules.technical_devices.repository import get_technical_device

router = APIRouter(prefix="/api/contracts", tags=["contracts"])
reference_router = APIRouter(prefix="/api/reference", tags=["reference"])
service = ContractService()


def _contract_or_404(
    db: Session,
    contract_id: uuid.UUID,
    *,
    ctx: AuthorizationContext,
    include_deleted: bool = False,
) -> Contract:
    contract = repository.get_contract(
        db,
        contract_id,
        include_deleted=include_deleted,
        authorization=ctx,
    )
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    return contract


def _permission_context_or_none(
    db: Session,
    *,
    user_id: uuid.UUID,
    permission_code: str,
) -> AuthorizationContext | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    if user.is_superuser:
        return build_authorization_context(
            user=user,
            permission_code=permission_code,
            grants=[],
        )

    grants = get_active_permission_scope_grants(
        db,
        user_id=user.id,
        permission_code=permission_code,
    )
    if not grants:
        return None

    return build_authorization_context(
        user=user,
        permission_code=permission_code,
        grants=grants,
    )


def _subject_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Contract subject not found",
    )


def _require_subject_access(
    db: Session,
    *,
    actor_ctx: AuthorizationContext,
    technical_device_ids: list[uuid.UUID],
    building_ids: list[uuid.UUID],
) -> None:
    if technical_device_ids:
        device_ctx = _permission_context_or_none(
            db,
            user_id=actor_ctx.user_id,
            permission_code="technical_devices.view",
        )
        if device_ctx is None:
            raise _subject_not_found()
        for device_id in set(technical_device_ids):
            device = get_technical_device(db, device_id)
            if device is None or not can_access_technical_device(device_ctx, device):
                raise _subject_not_found()

    if building_ids:
        building_ctx = _permission_context_or_none(
            db,
            user_id=actor_ctx.user_id,
            permission_code="buildings.view",
        )
        if building_ctx is None:
            raise _subject_not_found()
        for building_id in set(building_ids):
            building = get_building(db, building_id)
            if building is None or not can_access_building(building_ctx, building):
                raise _subject_not_found()


def _item_response(db: Session, item) -> ContractItemResponse:
    technical_device_ids, building_ids = repository.get_contract_item_subject_ids(
        db,
        item.id,
    )
    return ContractItemResponse(
        id=item.id,
        contract_id=item.contract_id,
        name=item.name,
        expertise_type_id=item.expertise_type_id,
        price=item.price,
        currency=item.currency,
        comment=item.comment,
        technical_device_ids=technical_device_ids,
        building_ids=building_ids,
        created_at=item.created_at,
        updated_at=item.updated_at,
        deleted_at=item.deleted_at,
        version=item.version,
    )


@router.get("", response_model=ContractPaginatedResponse)
def read_contracts(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    items, total = repository.list_contracts_paginated(
        db,
        q=q,
        page=page,
        page_size=page_size,
        authorization=ctx,
    )
    return ContractPaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.create")),
    db: Session = Depends(get_db),
):
    if not can_reference_organizations(ctx, payload.customer_organization_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    try:
        return service.create_contract(
            db,
            actor_id=ctx.user_id,
            customer_organization_id=payload.customer_organization_id,
            customer_contact_id=payload.customer_contact_id,
            number=payload.number,
            contract_date=payload.contract_date,
            start_date=payload.start_date,
            end_date=payload.end_date,
            comment=payload.comment,
        )
    except ContractValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{contract_id}", response_model=ContractResponse)
def read_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    return _contract_or_404(db, contract_id, ctx=ctx)


@router.put(
    "/{contract_id}/responsibles",
    response_model=ContractResponsiblesResponse,
)
def replace_contract_responsibles(
    contract_id: uuid.UUID,
    payload: ContractResponsiblesReplace,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_responsibles")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    try:
        employee_ids = service.replace_responsibles(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            employee_ids=payload.employee_ids,
        )
    except ContractValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ContractResponsiblesResponse(employee_ids=employee_ids)


@router.post(
    "/{contract_id}/items",
    response_model=ContractItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_item(
    contract_id: uuid.UUID,
    payload: ContractItemCreate,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_items")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    _require_subject_access(
        db,
        actor_ctx=ctx,
        technical_device_ids=payload.technical_device_ids,
        building_ids=payload.building_ids,
    )
    try:
        item = service.create_item(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            name=payload.name,
            expertise_type_id=payload.expertise_type_id,
            price=payload.price,
            technical_device_ids=payload.technical_device_ids,
            building_ids=payload.building_ids,
            comment=payload.comment,
        )
    except ContractValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _item_response(db, item)


@reference_router.get(
    "/expertise-types",
    response_model=list[ExpertiseTypeResponse],
)
def read_expertise_types(
    _ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    return repository.list_active_expertise_types(db)
