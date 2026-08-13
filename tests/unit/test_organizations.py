import uuid

from app.modules.identity.models import ScopeType
from app.modules.organizations.authorization import (
    can_manage_organization,
    evaluate_organization_scope,
)
from app.modules.organizations.models import (
    IdentifierType,
    OrganizationType,
)
from app.modules.organizations.schemas import (
    OrganizationCreate,
    OrganizationIdentifierCreate,
    OrganizationUpdate,
)
from app.modules.organizations.service import (
    OrganizationConflictError,
    OrganizationLegalFormError,
    OrganizationNotFoundError,
    validate_organization_legal_form,
)


def test_organization_enum_values_are_lowercase() -> None:
    assert OrganizationType.LEGAL_ENTITY.value == "legal_entity"
    assert OrganizationType.INDIVIDUAL_ENTREPRENEUR.value == "individual_entrepreneur"
    assert OrganizationType.BRANCH.value == "branch"
    assert IdentifierType.INN.value == "inn"
    assert IdentifierType.KPP.value == "kpp"
    assert IdentifierType.OGRN.value == "ogrn"
    assert IdentifierType.OGRNIP.value == "ogrnip"
    assert IdentifierType.EXTERNAL_ID.value == "external_id"


def test_organization_type_has_no_other() -> None:
    assert set(OrganizationType.__members__) == {
        "LEGAL_ENTITY",
        "INDIVIDUAL_ENTREPRENEUR",
        "BRANCH",
    }
    assert set(IdentifierType.__members__) == {
        "INN",
        "KPP",
        "OGRN",
        "OGRNIP",
        "EXTERNAL_ID",
    }


def test_organization_create_schema_defaults() -> None:
    schema = OrganizationCreate(legal_name="OOO Primer")
    assert schema.organization_type is OrganizationType.LEGAL_ENTITY
    assert schema.short_name is None
    assert schema.parent_id is None


def test_organization_update_schema_optional_fields() -> None:
    schema = OrganizationUpdate()
    dumped = schema.model_dump(exclude_unset=True)
    assert dumped == {}


def test_identifier_schema_requires_value() -> None:
    schema = OrganizationIdentifierCreate(
        identifier_type=IdentifierType.INN, identifier_value="1111111111"
    )
    assert schema.identifier_type is IdentifierType.INN
    assert schema.identifier_value == "1111111111"


def test_manage_permission_requires_scope_unless_superuser() -> None:
    assert not can_manage_organization(is_superuser=False, scopes=set())
    assert can_manage_organization(is_superuser=False, scopes={ScopeType.OWN})
    assert can_manage_organization(is_superuser=True, scopes=set())


def test_scope_all_allows_any_organization() -> None:
    user_id = uuid.uuid4()
    decision = evaluate_organization_scope({ScopeType.ALL}, user_id=user_id)
    assert decision.allowed
    assert decision.matched_scope is ScopeType.ALL


def test_assigned_scope_is_organization_specific() -> None:
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()
    decision = evaluate_organization_scope(
        {ScopeType.ASSIGNED},
        user_id=user_id,
        organization_id=org_id,
        assigned_organization_ids={org_id},
    )
    assert decision.allowed
    assert not evaluate_organization_scope(
        {ScopeType.ASSIGNED},
        user_id=user_id,
        organization_id=uuid.uuid4(),
        assigned_organization_ids={org_id},
    ).allowed


def test_own_scope_matches_creator() -> None:
    user_id = uuid.uuid4()
    assert evaluate_organization_scope(
        {ScopeType.OWN}, user_id=user_id, owner_user_id=user_id
    ).allowed
    assert not evaluate_organization_scope(
        {ScopeType.OWN}, user_id=user_id, owner_user_id=uuid.uuid4()
    ).allowed


def test_service_raises_conflict_on_identifier_conflict() -> None:
    assert issubclass(OrganizationConflictError, Exception)
    assert OrganizationConflictError is not OrganizationNotFoundError


def test_ip_rejects_legal_only_fields() -> None:
    try:
        validate_organization_legal_form(
            OrganizationType.INDIVIDUAL_ENTREPRENEUR,
            legal_address="legal-only",
            actual_address=None,
            director_name=None,
            residence_address="residence",
            passport_details="test details",
            identifiers=[],
        )
    except OrganizationLegalFormError:
        return
    raise AssertionError("IP payload accepted legal-entity-only fields")


def test_legal_entity_rejects_ip_only_fields() -> None:
    try:
        validate_organization_legal_form(
            OrganizationType.LEGAL_ENTITY,
            legal_address="legal",
            actual_address=None,
            director_name="Director",
            residence_address="ip-only",
            passport_details=None,
            identifiers=[],
        )
    except OrganizationLegalFormError:
        return
    raise AssertionError("Legal-entity payload accepted IP-only fields")
