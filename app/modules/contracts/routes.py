import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.modules.buildings.repository import get_building
from app.modules.contracts import repository
from app.modules.contracts.addenda import ContractAddendumService
from app.modules.contracts.enums import ContractStatus
from app.modules.contracts.lifecycle import ContractLifecycleService
from app.modules.contracts.models import Contract, ContractAddendum, ContractItem
from app.modules.contracts.schemas import (
    CompletionBlockerResponse,
    CompletionCheckResponse,
    ContractAddendumCreate,
    ContractAddendumResponse,
    ContractAddendumStatusChange,
    ContractAddendumUpdate,
    ContractCompletionReadinessResponse,
    ContractCreate,
    ContractItemCreate,
    ContractItemResponse,
    ContractItemUpdate,
    ContractPaginatedResponse,
    ContractReasonCommand,
    ContractResponse,
    ContractResponsiblesReplace,
    ContractResponsiblesResponse,
    ContractStatusChange,
    ContractUpdate,
    ExpertiseTypeResponse,
)
from app.modules.contracts.service import ContractService, ContractValidationError
from app.modules.identity.authorization import (
    AuthorizationContext,
    build_authorization_context,
    can_access_building,
    can_access_contract,
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
lifecycle_service = ContractLifecycleService()
addendum_service = ContractAddendumService()


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
    )
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    responsible_employee_ids = repository.get_contract_responsible_ids(db, contract.id)
    if not can_access_contract(
        ctx,
        contract,
        responsible_employee_ids=responsible_employee_ids,
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    return contract


def _locked_contract_or_404(db: Session, contract: Contract) -> Contract:
    locked = repository.get_contract_for_update(db, contract.id)
    if locked is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    return locked


def _item_or_404(
    db: Session,
    contract_id: uuid.UUID,
    item_id: uuid.UUID,
) -> ContractItem:
    item = repository.get_contract_item(db, contract_id, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract item not found",
        )
    return item


def _addendum_or_404(
    db: Session,
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
) -> ContractAddendum:
    addendum = repository.get_contract_addendum(db, contract_id, addendum_id)
    if addendum is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contract not found",
        )
    return addendum


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


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


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


def _item_response(db: Session, item: ContractItem) -> ContractItemResponse:
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


def _readiness_response(contract: Contract) -> ContractCompletionReadinessResponse:
    readiness = lifecycle_service.get_completion_readiness(
        _readiness_response.db,
        contract=contract,
    )
    return ContractCompletionReadinessResponse(
        ready_to_complete=readiness.ready_to_complete,
        checks=[
            CompletionCheckResponse(
                key=check.key,
                passed=check.passed,
                blockers=[
                    CompletionBlockerResponse(code=blocker.code, detail=blocker.detail)
                    for blocker in check.blockers
                ],
            )
            for check in readiness.checks
        ],
        blockers=[
            CompletionBlockerResponse(code=blocker.code, detail=blocker.detail)
            for blocker in readiness.blockers
        ],
    )


@router.get("", response_model=ContractPaginatedResponse)
def read_contracts(
    q: str = "",
    customer_organization_id: uuid.UUID | None = None,
    contract_status: Annotated[
        ContractStatus | None,
        Query(alias="status"),
    ] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    items, total = repository.list_contracts_paginated(
        db,
        q=q,
        customer_organization_id=customer_organization_id,
        contract_status=contract_status,
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
        raise _unprocessable(str(exc)) from exc


@router.get("/{contract_id}", response_model=ContractResponse)
def read_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    return _contract_or_404(db, contract_id, ctx=ctx)


@router.patch("/{contract_id}", response_model=ContractResponse)
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.edit")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    fields = payload.model_fields_set

    customer_organization_id = contract.customer_organization_id
    if "customer_organization_id" in fields:
        if payload.customer_organization_id is None:
            raise _unprocessable("Заказчик обязателен")
        if not can_reference_organizations(ctx, payload.customer_organization_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found",
            )
        customer_organization_id = payload.customer_organization_id

    if "number" in fields and payload.number is None:
        raise _unprocessable("Номер договора обязателен")
    if "contract_date" in fields and payload.contract_date is None:
        raise _unprocessable("Дата договора обязательна")

    customer_contact_id = (
        payload.customer_contact_id
        if "customer_contact_id" in fields
        else contract.customer_contact_id
    )
    number = payload.number if "number" in fields else contract.number
    contract_date = (
        payload.contract_date if "contract_date" in fields else contract.contract_date
    )
    start_date = payload.start_date if "start_date" in fields else contract.start_date
    end_date = payload.end_date if "end_date" in fields else contract.end_date
    comment = payload.comment if "comment" in fields else contract.comment

    try:
        return service.update_contract(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            customer_organization_id=customer_organization_id,
            customer_contact_id=customer_contact_id,
            number=number,
            contract_date=contract_date,
            start_date=start_date,
            end_date=end_date,
            comment=comment,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.delete")),
    db: Session = Depends(get_db),
) -> Response:
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    try:
        service.delete_contract(db, actor_id=ctx.user_id, contract=contract)
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{contract_id}/restore", response_model=ContractResponse)
def restore_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.restore")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx, include_deleted=True)
    try:
        service.restore_contract(db, actor_id=ctx.user_id, contract=contract)
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    db.refresh(contract)
    return contract


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
        raise _unprocessable(str(exc)) from exc
    return ContractResponsiblesResponse(employee_ids=employee_ids)


@router.get(
    "/{contract_id}/items",
    response_model=list[ContractItemResponse],
)
def read_contract_items(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    return [
        _item_response(db, item)
        for item in repository.list_contract_items(db, contract.id)
    ]


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
        raise _unprocessable(str(exc)) from exc
    return _item_response(db, item)


@router.patch(
    "/{contract_id}/items/{item_id}",
    response_model=ContractItemResponse,
)
def update_contract_item(
    contract_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ContractItemUpdate,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_items")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    item = _item_or_404(db, contract_id, item_id)
    fields = payload.model_fields_set

    if "name" in fields and payload.name is None:
        raise _unprocessable("Наименование предмета договора обязательно")
    if "expertise_type_id" in fields and payload.expertise_type_id is None:
        raise _unprocessable("Тип экспертизы обязателен")
    if "price" in fields and payload.price is None:
        raise _unprocessable("Стоимость предмета договора обязательна")
    if "technical_device_ids" in fields and payload.technical_device_ids is None:
        raise _unprocessable("Список технических устройств должен быть массивом")
    if "building_ids" in fields and payload.building_ids is None:
        raise _unprocessable("Список зданий должен быть массивом")

    current_device_ids, current_building_ids = repository.get_contract_item_subject_ids(
        db,
        item.id,
    )
    technical_device_ids = (
        payload.technical_device_ids
        if "technical_device_ids" in fields
        else current_device_ids
    )
    building_ids = payload.building_ids if "building_ids" in fields else current_building_ids
    _require_subject_access(
        db,
        actor_ctx=ctx,
        technical_device_ids=technical_device_ids,
        building_ids=building_ids,
    )

    try:
        item = service.update_item(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            item=item,
            name=payload.name if "name" in fields else item.name,
            expertise_type_id=(
                payload.expertise_type_id
                if "expertise_type_id" in fields
                else item.expertise_type_id
            ),
            price=payload.price if "price" in fields else item.price,
            technical_device_ids=technical_device_ids,
            building_ids=building_ids,
            comment=payload.comment if "comment" in fields else item.comment,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return _item_response(db, item)


@router.delete(
    "/{contract_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_contract_item(
    contract_id: uuid.UUID,
    item_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_items")
    ),
    db: Session = Depends(get_db),
) -> Response:
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    item = _item_or_404(db, contract_id, item_id)
    try:
        service.delete_item(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            item=item,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{contract_id}/status", response_model=ContractResponse)
def change_contract_status(
    contract_id: uuid.UUID,
    payload: ContractStatusChange,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.change_status")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    contract = _locked_contract_or_404(db, contract)
    try:
        return lifecycle_service.change_status(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            target_status=payload.status,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.post("/{contract_id}/suspend", response_model=ContractResponse)
def suspend_contract(
    contract_id: uuid.UUID,
    payload: ContractReasonCommand,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.change_status")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    contract = _locked_contract_or_404(db, contract)
    try:
        lifecycle_service.suspend(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            reason=payload.reason,
        )
        db.refresh(contract)
        return contract
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.post("/{contract_id}/resume", response_model=ContractResponse)
def resume_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.change_status")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    contract = _locked_contract_or_404(db, contract)
    try:
        lifecycle_service.resume(db, actor_id=ctx.user_id, contract=contract)
        db.refresh(contract)
        return contract
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.post("/{contract_id}/terminate", response_model=ContractResponse)
def terminate_contract(
    contract_id: uuid.UUID,
    payload: ContractReasonCommand,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.terminate")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    contract = _locked_contract_or_404(db, contract)
    try:
        return lifecycle_service.terminate(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            reason=payload.reason,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.get(
    "/{contract_id}/completion-readiness",
    response_model=ContractCompletionReadinessResponse,
)
def read_contract_completion_readiness(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    readiness = lifecycle_service.get_completion_readiness(db, contract=contract)
    return ContractCompletionReadinessResponse(
        ready_to_complete=readiness.ready_to_complete,
        checks=[
            CompletionCheckResponse(
                key=check.key,
                passed=check.passed,
                blockers=[
                    CompletionBlockerResponse(code=blocker.code, detail=blocker.detail)
                    for blocker in check.blockers
                ],
            )
            for check in readiness.checks
        ],
        blockers=[
            CompletionBlockerResponse(code=blocker.code, detail=blocker.detail)
            for blocker in readiness.blockers
        ],
    )


@router.post("/{contract_id}/complete", response_model=ContractResponse)
def complete_contract(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.complete")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    contract = _locked_contract_or_404(db, contract)
    try:
        return lifecycle_service.complete(
            db,
            actor_id=ctx.user_id,
            contract=contract,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.get(
    "/{contract_id}/addenda",
    response_model=list[ContractAddendumResponse],
)
def read_contract_addenda(
    contract_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    return repository.list_contract_addenda(db, contract.id)


@router.post(
    "/{contract_id}/addenda",
    response_model=ContractAddendumResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_contract_addendum(
    contract_id: uuid.UUID,
    payload: ContractAddendumCreate,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_addenda")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    try:
        return addendum_service.create_addendum(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            number=payload.number,
            addendum_date=payload.addendum_date,
            amount_delta=payload.amount_delta,
            new_end_date=payload.new_end_date,
            description=payload.description,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.get(
    "/{contract_id}/addenda/{addendum_id}",
    response_model=ContractAddendumResponse,
)
def read_contract_addendum(
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    return _addendum_or_404(db, contract.id, addendum_id)


@router.patch(
    "/{contract_id}/addenda/{addendum_id}",
    response_model=ContractAddendumResponse,
)
def update_contract_addendum(
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    payload: ContractAddendumUpdate,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_addenda")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    addendum = _addendum_or_404(db, contract.id, addendum_id)
    fields = payload.model_fields_set

    if "number" in fields and payload.number is None:
        raise _unprocessable("Номер дополнительного соглашения обязателен")
    if "addendum_date" in fields and payload.addendum_date is None:
        raise _unprocessable("Дата дополнительного соглашения обязательна")

    try:
        return addendum_service.update_addendum(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            addendum=addendum,
            number=payload.number if "number" in fields else addendum.number,
            addendum_date=(
                payload.addendum_date
                if "addendum_date" in fields
                else addendum.addendum_date
            ),
            amount_delta=(
                payload.amount_delta
                if "amount_delta" in fields
                else addendum.amount_delta
            ),
            new_end_date=(
                payload.new_end_date
                if "new_end_date" in fields
                else addendum.new_end_date
            ),
            description=(
                payload.description
                if "description" in fields
                else addendum.description
            ),
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@router.delete(
    "/{contract_id}/addenda/{addendum_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_contract_addendum(
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_addenda")
    ),
    db: Session = Depends(get_db),
) -> Response:
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    addendum = _addendum_or_404(db, contract.id, addendum_id)
    try:
        addendum_service.delete_addendum(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            addendum=addendum,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{contract_id}/addenda/{addendum_id}/status",
    response_model=ContractAddendumResponse,
)
def change_contract_addendum_status(
    contract_id: uuid.UUID,
    addendum_id: uuid.UUID,
    payload: ContractAddendumStatusChange,
    ctx: AuthorizationContext = Depends(
        require_scoped_permission("contracts.manage_addenda")
    ),
    db: Session = Depends(get_db),
):
    contract = _contract_or_404(db, contract_id, ctx=ctx)
    addendum = _addendum_or_404(db, contract.id, addendum_id)
    try:
        return addendum_service.change_status(
            db,
            actor_id=ctx.user_id,
            contract=contract,
            addendum=addendum,
            target_status=payload.status,
        )
    except ContractValidationError as exc:
        raise _unprocessable(str(exc)) from exc


@reference_router.get(
    "/expertise-types",
    response_model=list[ExpertiseTypeResponse],
)
def read_expertise_types(
    _ctx: AuthorizationContext = Depends(require_scoped_permission("contracts.view")),
    db: Session = Depends(get_db),
):
    return repository.list_active_expertise_types(db)
