"""Targeted tests for import matching logic (branch scenarios)."""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.modules.import_.enums import CandidateAction, CandidateStatus
from app.modules.import_.service import _determine_status_and_action, match_organization
from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.models import Organization, OrganizationIdentifier


@pytest.fixture()
def db_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_engine(url)
    yield engine
    engine.dispose()


def _create_org(session: Session, org_type: OrganizationType, name: str) -> Organization:
    org = Organization(
        organization_type=org_type,
        legal_name=name,
    )
    session.add(org)
    session.flush()
    return org


def _add_identifier(
    session: Session,
    org: Organization,
    id_type: IdentifierType,
    value: str,
    is_primary: bool = False,
) -> OrganizationIdentifier:
    ident = OrganizationIdentifier(
        organization_id=org.id,
        identifier_type=id_type,
        identifier_value=value,
        is_primary=is_primary,
    )
    session.add(ident)
    session.flush()
    return ident


def _rand_inn() -> str:
    return f"{uuid.uuid4().int % 10**10:010d}"


def _rand_kpp() -> str:
    return f"{uuid.uuid4().int % 10**9:09d}"


@pytest.mark.integration
def test_branch_exact_inn_kpp_match(db_engine) -> None:
    """BRANCH with INN+KPP matching existing branch -> exact_inn_kpp -> UPDATE."""
    shared_inn = _rand_inn()
    shared_kpp = _rand_kpp()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch1 = _create_org(session, OrganizationType.BRANCH, "Branch 1")
        _add_identifier(session, branch1, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch1, IdentifierType.KPP, shared_kpp)
        _add_identifier(session, branch1, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import branch with same INN+KPP -> exact match
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.BRANCH,
            "inn": shared_inn,
            "kpp": shared_kpp,
        })
        assert match_org is not None
        assert match_org.id == branch1.id
        assert match_type == "exact_inn_kpp"

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.UPDATE
        assert action == CandidateAction.UPDATE


@pytest.mark.integration
def test_branch_inn_only_no_kpp_potential_duplicate(db_engine) -> None:
    """BRANCH with INN only (no KPP) -> ambiguous_inn -> POTENTIAL_DUPLICATE."""
    shared_inn = _rand_inn()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch1 = _create_org(session, OrganizationType.BRANCH, "Branch 1")
        _add_identifier(session, branch1, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch1, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, branch1, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import branch with same INN but no KPP -> ambiguous
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.BRANCH,
            "inn": shared_inn,
            "kpp": None,
        })
        assert match_type == "ambiguous_inn"

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.POTENTIAL_DUPLICATE
        assert action == CandidateAction.SKIP


@pytest.mark.integration
def test_branch_inn_match_kpp_mismatch_potential_duplicate(db_engine) -> None:
    """BRANCH with INN matching but KPP different -> ambiguous_inn -> POTENTIAL_DUPLICATE."""
    shared_inn = _rand_inn()
    kpp1 = _rand_kpp()
    kpp2 = _rand_kpp()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch1 = _create_org(session, OrganizationType.BRANCH, "Branch 1")
        _add_identifier(session, branch1, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch1, IdentifierType.KPP, kpp1)
        _add_identifier(session, branch1, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import branch with same INN but different KPP -> ambiguous
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.BRANCH,
            "inn": shared_inn,
            "kpp": kpp2,
        })
        assert match_type == "ambiguous_inn"

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.POTENTIAL_DUPLICATE
        assert action == CandidateAction.SKIP


@pytest.mark.integration
def test_branch_multiple_same_inn_no_auto_match(db_engine) -> None:
    """Multiple branches with same INN -> import should not auto-match any."""
    shared_inn = _rand_inn()
    kpp1 = _rand_kpp()
    kpp2 = _rand_kpp()
    kpp3 = _rand_kpp()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch1 = _create_org(session, OrganizationType.BRANCH, "Branch 1")
        _add_identifier(session, branch1, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch1, IdentifierType.KPP, kpp1)
        _add_identifier(session, branch1, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch2 = _create_org(session, OrganizationType.BRANCH, "Branch 2")
        _add_identifier(session, branch2, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch2, IdentifierType.KPP, kpp2)
        _add_identifier(session, branch2, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import branch with same INN but KPP matching neither -> ambiguous
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.BRANCH,
            "inn": shared_inn,
            "kpp": kpp3,
        })
        assert match_type == "ambiguous_inn"
        assert match_org is None

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.POTENTIAL_DUPLICATE
        assert action == CandidateAction.SKIP


@pytest.mark.integration
def test_legal_entity_inn_only_unambiguous(db_engine) -> None:
    """LEGAL_ENTITY with INN only when single org has this INN -> exact_inn -> UPDATE."""
    unique_inn = _rand_inn()

    with Session(db_engine) as session:
        le = _create_org(session, OrganizationType.LEGAL_ENTITY, "LE")
        _add_identifier(session, le, IdentifierType.INN, unique_inn)
        _add_identifier(session, le, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import LE with same INN (no KPP provided) -> exact match
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.LEGAL_ENTITY,
            "inn": unique_inn,
            "kpp": None,
        })
        assert match_org is not None
        assert match_org.id == le.id
        assert match_type == "exact_inn"

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.UPDATE
        assert action == CandidateAction.UPDATE


@pytest.mark.integration
def test_legal_entity_inn_ambiguous_due_to_branches(db_engine) -> None:
    """LEGAL_ENTITY with INN shared by branches -> ambiguous_inn -> POTENTIAL_DUPLICATE."""
    shared_inn = _rand_inn()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        branch1 = _create_org(session, OrganizationType.BRANCH, "Branch 1")
        _add_identifier(session, branch1, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch1, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, branch1, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import LE with same INN but no KPP -> ambiguous (multiple orgs have this INN)
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.LEGAL_ENTITY,
            "inn": shared_inn,
            "kpp": None,
        })
        assert match_type == "ambiguous_inn"
        assert match_org is None

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.POTENTIAL_DUPLICATE
        assert action == CandidateAction.SKIP


@pytest.mark.integration
def test_legal_entity_inn_kpp_exact_match(db_engine) -> None:
    """LEGAL_ENTITY with INN+KPP matching parent -> exact_inn_kpp -> UPDATE."""
    shared_inn = _rand_inn()
    shared_kpp = _rand_kpp()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, shared_kpp)
        _add_identifier(session, parent, IdentifierType.OGRN, f"{uuid.uuid4().int % 10**13:013d}")

        session.commit()

        # Import LE with same INN+KPP -> exact match
        match_org, match_type = match_organization(session, {
            "organization_type": OrganizationType.LEGAL_ENTITY,
            "inn": shared_inn,
            "kpp": shared_kpp,
        })
        assert match_org is not None
        assert match_org.id == parent.id
        assert match_type == "exact_inn_kpp"

        status, action = _determine_status_and_action(match_org, match_type, [])
        assert status == CandidateStatus.UPDATE
        assert action == CandidateAction.UPDATE