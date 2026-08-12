import uuid
from types import SimpleNamespace

from app.modules.identity.authorization import (
    AuthorizationContext,
    can_access_contract,
    evaluate_scopes,
    has_permission,
)
from app.modules.identity.models import ScopeType


def test_scope_all_allows_any_resource() -> None:
    user_id = uuid.uuid4()
    decision = evaluate_scopes(
        {ScopeType.ALL},
        user_id=user_id,
    )

    assert decision.allowed
    assert decision.matched_scope is ScopeType.ALL


def test_own_assigned_and_related_are_resource_specific() -> None:
    user_id = uuid.uuid4()
    other = uuid.uuid4()

    assert evaluate_scopes(
        {ScopeType.OWN},
        user_id=user_id,
        owner_user_id=user_id,
    ).allowed

    assert not evaluate_scopes(
        {ScopeType.OWN},
        user_id=user_id,
        owner_user_id=other,
    ).allowed

    assert evaluate_scopes(
        {ScopeType.ASSIGNED},
        user_id=user_id,
        assigned_user_ids={user_id},
    ).allowed

    assert evaluate_scopes(
        {ScopeType.RELATED},
        user_id=user_id,
        related_user_ids={user_id},
    ).allowed


def test_permission_requires_scope_unless_superuser() -> None:
    assert not has_permission(
        is_superuser=False,
        scopes=set(),
    )

    assert has_permission(
        is_superuser=False,
        scopes={ScopeType.OWN},
    )

    assert has_permission(
        is_superuser=True,
        scopes=set(),
    )


def _contract_ctx(
    scope_type: ScopeType,
    *,
    user_id: uuid.UUID,
    employee_id: uuid.UUID,
    related_organization_ids: frozenset[uuid.UUID] = frozenset(),
) -> AuthorizationContext:
    return AuthorizationContext(
        user_id=user_id,
        employee_id=employee_id,
        permission_code="contracts.view",
        is_superuser=False,
        has_all_scope=scope_type is ScopeType.ALL,
        related_organization_ids=related_organization_ids,
        active_scope_types=frozenset({scope_type}),
    )


def test_contract_scope_policy_covers_all_related_assigned_and_own() -> None:
    user_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    customer_id = uuid.uuid4()
    contract = SimpleNamespace(
        customer_organization_id=customer_id,
        created_by=user_id,
    )

    assert can_access_contract(
        _contract_ctx(
            ScopeType.ALL,
            user_id=user_id,
            employee_id=employee_id,
        ),
        contract,
        responsible_employee_ids=set(),
    )
    assert can_access_contract(
        _contract_ctx(
            ScopeType.RELATED,
            user_id=user_id,
            employee_id=employee_id,
            related_organization_ids=frozenset({customer_id}),
        ),
        contract,
        responsible_employee_ids=set(),
    )
    assert can_access_contract(
        _contract_ctx(
            ScopeType.ASSIGNED,
            user_id=user_id,
            employee_id=employee_id,
        ),
        contract,
        responsible_employee_ids={employee_id},
    )
    assert can_access_contract(
        _contract_ctx(
            ScopeType.OWN,
            user_id=user_id,
            employee_id=employee_id,
        ),
        contract,
        responsible_employee_ids=set(),
    )


def test_contract_scope_policy_fails_closed_when_resource_does_not_match() -> None:
    user_id = uuid.uuid4()
    employee_id = uuid.uuid4()
    contract = SimpleNamespace(
        customer_organization_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
    )

    assert not can_access_contract(
        _contract_ctx(
            ScopeType.RELATED,
            user_id=user_id,
            employee_id=employee_id,
            related_organization_ids=frozenset({uuid.uuid4()}),
        ),
        contract,
        responsible_employee_ids={uuid.uuid4()},
    )
    assert not can_access_contract(
        _contract_ctx(
            ScopeType.ASSIGNED,
            user_id=user_id,
            employee_id=employee_id,
        ),
        contract,
        responsible_employee_ids={uuid.uuid4()},
    )
    assert not can_access_contract(
        _contract_ctx(
            ScopeType.OWN,
            user_id=user_id,
            employee_id=employee_id,
        ),
        contract,
        responsible_employee_ids=set(),
    )
