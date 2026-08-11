import uuid

from app.modules.identity.authorization import evaluate_scopes, has_permission
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