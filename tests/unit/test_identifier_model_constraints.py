"""Tests for identifier model constraints after migration 0020.

Cases:
A: Two LEs can have different INNs
B: Two LEs can share the same INN with different KPPs (parent + branch)
C: Two LEs cannot have the same OGRN
D: An LE and a Branch can share the same INN (parent + filial)
E: One org cannot have two identifiers of the same type
F: One org can have INN + KPP + OGRN (different types)
G: Two IPs cannot have the same OGRNIP
H: An IP's INN can match an LE's INN
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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


def _rand_inn() -> str:
    return f"{uuid.uuid4().int % 10**10:010d}"


def _rand_ogrn() -> str:
    return f"{uuid.uuid4().int % 10**13:013d}"


def _rand_ogrnip() -> str:
    return f"{uuid.uuid4().int % 10**15:015d}"


def _rand_kpp() -> str:
    return f"{uuid.uuid4().int % 10**9:09d}"


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


def _get_identifiers(session: Session, org: Organization) -> list[OrganizationIdentifier]:
    return list(
        session.scalars(
            select(OrganizationIdentifier).where(
                OrganizationIdentifier.organization_id == org.id
            )
        )
    )


@pytest.mark.integration
def test_case_a_two_le_different_inns(db_engine) -> None:
    with Session(db_engine) as session:
        org1 = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org A1")
        _add_identifier(session, org1, IdentifierType.INN, _rand_inn())
        _add_identifier(session, org1, IdentifierType.OGRN, _rand_ogrn())

        org2 = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org A2")
        _add_identifier(session, org2, IdentifierType.INN, _rand_inn())
        _add_identifier(session, org2, IdentifierType.OGRN, _rand_ogrn())

        session.commit()
        assert org1.id != org2.id


@pytest.mark.integration
def test_case_b_two_le_same_inn_different_kpp(db_engine) -> None:
    shared_inn = _rand_inn()
    parent_ogrn = _rand_ogrn()
    branch_ogrn = _rand_ogrn()
    parent_kpp = _rand_kpp()
    branch_kpp = _rand_kpp()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent B")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.KPP, parent_kpp)
        _add_identifier(session, parent, IdentifierType.OGRN, parent_ogrn)

        branch = _create_org(session, OrganizationType.BRANCH, "Branch B")
        _add_identifier(session, branch, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch, IdentifierType.KPP, branch_kpp)
        _add_identifier(session, branch, IdentifierType.OGRN, branch_ogrn)

        session.commit()
        assert parent.id != branch.id


@pytest.mark.integration
def test_case_c_two_le_same_ogrn_fails(db_engine) -> None:
    shared_ogrn = _rand_ogrn()

    with Session(db_engine) as session:
        org1 = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org C1")
        _add_identifier(session, org1, IdentifierType.OGRN, shared_ogrn)
        _add_identifier(session, org1, IdentifierType.INN, _rand_inn())

        org2 = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org C2")
        _add_identifier(session, org2, IdentifierType.INN, _rand_inn())

        with pytest.raises(IntegrityError):
            _add_identifier(session, org2, IdentifierType.OGRN, shared_ogrn)


@pytest.mark.integration
def test_case_d_le_and_branch_same_inn(db_engine) -> None:
    shared_inn = _rand_inn()
    parent_ogrn = _rand_ogrn()
    branch_ogrn = _rand_ogrn()

    with Session(db_engine) as session:
        parent = _create_org(session, OrganizationType.LEGAL_ENTITY, "Parent D")
        _add_identifier(session, parent, IdentifierType.INN, shared_inn)
        _add_identifier(session, parent, IdentifierType.OGRN, parent_ogrn)

        branch = _create_org(session, OrganizationType.BRANCH, "Branch D")
        _add_identifier(session, branch, IdentifierType.INN, shared_inn)
        _add_identifier(session, branch, IdentifierType.OGRN, branch_ogrn)

        session.commit()
        assert parent.id != branch.id


@pytest.mark.integration
def test_case_e_org_cannot_have_two_same_type_identifiers(db_engine) -> None:
    with Session(db_engine) as session:
        org = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org E")
        _add_identifier(session, org, IdentifierType.INN, _rand_inn())

        with pytest.raises(IntegrityError):
            _add_identifier(session, org, IdentifierType.INN, _rand_inn())


@pytest.mark.integration
def test_case_f_org_can_have_inn_kpp_ogrn(db_engine) -> None:
    with Session(db_engine) as session:
        org = _create_org(session, OrganizationType.LEGAL_ENTITY, "Org F")
        _add_identifier(session, org, IdentifierType.INN, _rand_inn())
        _add_identifier(session, org, IdentifierType.KPP, _rand_kpp())
        _add_identifier(session, org, IdentifierType.OGRN, _rand_ogrn())

        session.commit()
        idents = _get_identifiers(session, org)
        assert len(idents) == 3


@pytest.mark.integration
def test_case_g_two_ips_same_ogrnip_fails(db_engine) -> None:
    shared_ogrnip = _rand_ogrnip()

    with Session(db_engine) as session:
        ip1 = _create_org(session, OrganizationType.INDIVIDUAL_ENTREPRENEUR, "IP G1")
        _add_identifier(session, ip1, IdentifierType.OGRNIP, shared_ogrnip)
        _add_identifier(session, ip1, IdentifierType.INN, _rand_inn())

        ip2 = _create_org(session, OrganizationType.INDIVIDUAL_ENTREPRENEUR, "IP G2")
        _add_identifier(session, ip2, IdentifierType.INN, _rand_inn())

        with pytest.raises(IntegrityError):
            _add_identifier(session, ip2, IdentifierType.OGRNIP, shared_ogrnip)


@pytest.mark.integration
def test_case_h_ip_inn_matches_le_inn(db_engine) -> None:
    shared_inn = _rand_inn()
    le_ogrn = _rand_ogrn()
    ip_ogrnip = _rand_ogrnip()

    with Session(db_engine) as session:
        le = _create_org(session, OrganizationType.LEGAL_ENTITY, "LE H")
        _add_identifier(session, le, IdentifierType.INN, shared_inn)
        _add_identifier(session, le, IdentifierType.OGRN, le_ogrn)

        ip = _create_org(session, OrganizationType.INDIVIDUAL_ENTREPRENEUR, "IP H")
        _add_identifier(session, ip, IdentifierType.INN, shared_inn)
        _add_identifier(session, ip, IdentifierType.OGRNIP, ip_ogrnip)

        session.commit()
        assert le.id != ip.id