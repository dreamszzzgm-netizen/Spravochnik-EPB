import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.buildings.repository import list_buildings_paginated
from app.modules.identity.authorization import AuthorizationContext
from app.modules.identity.models import ScopeType
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.opo.repository import list_opo_paginated
from app.modules.organizations.enums import OrganizationType
from app.modules.organizations.models import Organization
from app.modules.organizations.repository import (
    list_organizations_paginated,
)
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice
from app.modules.technical_devices.repository import (
    list_technical_devices_paginated,
)

pytestmark = pytest.mark.integration


def _context(
    *,
    allowed_organization_ids: set[uuid.UUID] | None = None,
    has_all_scope: bool = False,
    active_scope_types: set[ScopeType] | None = None,
) -> AuthorizationContext:
    if active_scope_types is None:
        active_scope_types = (
            {ScopeType.ALL}
            if has_all_scope
            else {ScopeType.RELATED}
        )

    return AuthorizationContext(
        user_id=uuid.uuid4(),
        employee_id=uuid.uuid4(),
        permission_code="test.view",
        is_superuser=False,
        has_all_scope=has_all_scope,
        related_organization_ids=frozenset(
            allowed_organization_ids or set()
        ),
        active_scope_types=frozenset(active_scope_types),
    )


def _organization(
    db: Session,
    *,
    legal_name: str,
    deleted: bool = False,
) -> Organization:
    organization = Organization(
        organization_type=OrganizationType.LEGAL_ENTITY,
        legal_name=legal_name,
        short_name=legal_name,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(organization)
    db.flush()
    return organization


def _opo(
    db: Session,
    *,
    name: str,
    owner_id: uuid.UUID,
    operator_id: uuid.UUID,
    deleted: bool = False,
) -> OPO:
    opo = OPO(
        name=name,
        registration_number=f"REG-{uuid.uuid4()}",
        hazard_class=HazardClass.HAZARD_CLASS_3,
        address=f"{name} address",
        registration_date=date(2026, 1, 1),
        owner_organization_id=owner_id,
        operating_organization_id=operator_id,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(opo)
    db.flush()
    return opo


def _technical_device(
    db: Session,
    *,
    name: str,
    organization_id: uuid.UUID | None,
    opo_id: uuid.UUID | None = None,
    deleted: bool = False,
) -> TechnicalDevice:
    device = TechnicalDevice(
        name=name,
        device_type=TechnicalDeviceType.OTHER,
        organization_id=organization_id,
        opo_id=opo_id,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(device)
    db.flush()
    return device


def _building(
    db: Session,
    *,
    name: str,
    organization_id: uuid.UUID | None,
    opo_id: uuid.UUID | None = None,
    deleted: bool = False,
) -> Building:
    building = Building(
        name=name,
        building_type=BuildingType.OTHER,
        organization_id=organization_id,
        opo_id=opo_id,
        deleted_at=datetime.now(UTC) if deleted else None,
    )
    db.add(building)
    db.flush()
    return building


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


def test_organizations_related_scope_filters_before_count_and_pagination(
    db_session: Session,
) -> None:
    allowed_alpha = _organization(
        db_session,
        legal_name="Alpha Allowed",
    )
    _organization(
        db_session,
        legal_name="Bravo Foreign",
    )
    allowed_charlie = _organization(
        db_session,
        legal_name="Charlie Allowed",
    )
    _organization(
        db_session,
        legal_name="Delta Foreign",
    )

    ctx = _context(
        allowed_organization_ids={
            allowed_alpha.id,
            allowed_charlie.id,
        }
    )

    page_1, total_1 = list_organizations_paginated(
        db_session,
        page=1,
        page_size=1,
        authorization=ctx,
    )
    page_2, total_2 = list_organizations_paginated(
        db_session,
        page=2,
        page_size=1,
        authorization=ctx,
    )

    assert total_1 == 2
    assert total_2 == 2
    assert [item.id for item in page_1] == [
        allowed_alpha.id
    ]
    assert [item.id for item in page_2] == [
        allowed_charlie.id
    ]

    foreign_search, foreign_total = (
        list_organizations_paginated(
            db_session,
            q="Foreign",
            authorization=ctx,
        )
    )

    assert foreign_search == []
    assert foreign_total == 0


def test_organizations_none_and_all_preserve_unrestricted_behavior(
    db_session: Session,
) -> None:
    first = _organization(
        db_session,
        legal_name="Alpha",
    )
    second = _organization(
        db_session,
        legal_name="Bravo",
    )

    unrestricted, unrestricted_total = (
        list_organizations_paginated(
            db_session,
            authorization=None,
        )
    )
    all_items, all_total = list_organizations_paginated(
        db_session,
        authorization=_context(
            has_all_scope=True,
        ),
    )

    assert unrestricted_total == 2
    assert all_total == 2
    assert {item.id for item in unrestricted} == {
        first.id,
        second.id,
    }
    assert {item.id for item in all_items} == {
        first.id,
        second.id,
    }


def test_organizations_empty_non_all_scope_returns_zero(
    db_session: Session,
) -> None:
    _organization(
        db_session,
        legal_name="Existing Organization",
    )

    ctx = _context(
        active_scope_types={
            ScopeType.ASSIGNED,
            ScopeType.OWN,
        },
    )

    items, total = list_organizations_paginated(
        db_session,
        authorization=ctx,
    )

    assert items == []
    assert total == 0


def test_organizations_scope_still_excludes_deleted_rows(
    db_session: Session,
) -> None:
    active = _organization(
        db_session,
        legal_name="Active Allowed",
    )
    deleted = _organization(
        db_session,
        legal_name="Deleted Allowed",
        deleted=True,
    )

    ctx = _context(
        allowed_organization_ids={
            active.id,
            deleted.id,
        }
    )

    items, total = list_organizations_paginated(
        db_session,
        authorization=ctx,
    )

    assert total == 1
    assert [item.id for item in items] == [active.id]


# ---------------------------------------------------------------------------
# OPO
# ---------------------------------------------------------------------------


def test_opo_related_scope_accepts_allowed_owner_or_operator(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_b = _organization(
        db_session,
        legal_name="Foreign B",
    )
    foreign_c = _organization(
        db_session,
        legal_name="Foreign C",
    )

    owner_allowed = _opo(
        db_session,
        name="Alpha Owner Allowed",
        owner_id=allowed_org.id,
        operator_id=foreign_b.id,
    )
    operator_allowed = _opo(
        db_session,
        name="Bravo Operator Allowed",
        owner_id=foreign_b.id,
        operator_id=allowed_org.id,
    )
    _opo(
        db_session,
        name="Charlie Foreign",
        owner_id=foreign_b.id,
        operator_id=foreign_c.id,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_opo_paginated(
        db_session,
        authorization=ctx,
    )

    assert total == 2
    assert [item.id for item in items] == [
        owner_allowed.id,
        operator_allowed.id,
    ]


def test_opo_user_organization_filter_is_anded_with_security_scope(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_b = _organization(
        db_session,
        legal_name="Foreign B",
    )
    foreign_c = _organization(
        db_session,
        legal_name="Foreign C",
    )

    accessible = _opo(
        db_session,
        name="Accessible Via Allowed Owner",
        owner_id=allowed_org.id,
        operator_id=foreign_b.id,
    )
    _opo(
        db_session,
        name="Foreign Match",
        owner_id=foreign_b.id,
        operator_id=foreign_c.id,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_opo_paginated(
        db_session,
        organization_id=foreign_b.id,
        authorization=ctx,
    )

    assert total == 1
    assert [item.id for item in items] == [accessible.id]


def test_opo_empty_non_all_scope_returns_zero(
    db_session: Session,
) -> None:
    org = _organization(
        db_session,
        legal_name="Org",
    )
    _opo(
        db_session,
        name="Existing OPO",
        owner_id=org.id,
        operator_id=org.id,
    )

    ctx = _context(
        active_scope_types={ScopeType.ASSIGNED},
    )

    items, total = list_opo_paginated(
        db_session,
        authorization=ctx,
    )

    assert items == []
    assert total == 0


def test_opo_deleted_behavior_is_preserved_with_scope(
    db_session: Session,
) -> None:
    org = _organization(
        db_session,
        legal_name="Org",
    )
    active = _opo(
        db_session,
        name="Active OPO",
        owner_id=org.id,
        operator_id=org.id,
    )
    deleted = _opo(
        db_session,
        name="Deleted OPO",
        owner_id=org.id,
        operator_id=org.id,
        deleted=True,
    )

    ctx = _context(
        allowed_organization_ids={org.id}
    )

    normal_items, normal_total = list_opo_paginated(
        db_session,
        authorization=ctx,
    )
    all_items, all_total = list_opo_paginated(
        db_session,
        include_deleted=True,
        authorization=ctx,
    )

    assert normal_total == 1
    assert [item.id for item in normal_items] == [active.id]

    assert all_total == 2
    assert {item.id for item in all_items} == {
        active.id,
        deleted.id,
    }


# ---------------------------------------------------------------------------
# Technical Devices
# ---------------------------------------------------------------------------


def test_technical_devices_related_scope_uses_own_organization_only(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_org = _organization(
        db_session,
        legal_name="Foreign Org",
    )

    allowed = _technical_device(
        db_session,
        name="Alpha Allowed Device",
        organization_id=allowed_org.id,
    )
    _technical_device(
        db_session,
        name="Bravo Foreign Device",
        organization_id=foreign_org.id,
    )
    _technical_device(
        db_session,
        name="Charlie Legacy Null Device",
        organization_id=None,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_technical_devices_paginated(
        db_session,
        authorization=ctx,
    )

    assert total == 1
    assert [item.id for item in items] == [allowed.id]

    foreign_items, foreign_total = (
        list_technical_devices_paginated(
            db_session,
            organization_id=foreign_org.id,
            authorization=ctx,
        )
    )

    assert foreign_items == []
    assert foreign_total == 0


def test_technical_devices_all_and_unrestricted_see_legacy_null(
    db_session: Session,
) -> None:
    org = _organization(
        db_session,
        legal_name="Org",
    )

    normal = _technical_device(
        db_session,
        name="Normal Device",
        organization_id=org.id,
    )
    legacy = _technical_device(
        db_session,
        name="Legacy Device",
        organization_id=None,
    )

    unrestricted, unrestricted_total = (
        list_technical_devices_paginated(
            db_session,
            authorization=None,
        )
    )
    all_items, all_total = (
        list_technical_devices_paginated(
            db_session,
            authorization=_context(
                has_all_scope=True,
            ),
        )
    )

    assert unrestricted_total == 2
    assert all_total == 2
    assert {item.id for item in unrestricted} == {
        normal.id,
        legacy.id,
    }
    assert {item.id for item in all_items} == {
        normal.id,
        legacy.id,
    }


def test_technical_device_search_cannot_broaden_related_scope(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_org = _organization(
        db_session,
        legal_name="Foreign Org",
    )

    _technical_device(
        db_session,
        name="Foreign Search Match",
        organization_id=foreign_org.id,
    )
    _technical_device(
        db_session,
        name="Allowed Different Name",
        organization_id=allowed_org.id,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_technical_devices_paginated(
        db_session,
        q="Foreign Search Match",
        authorization=ctx,
    )

    assert items == []
    assert total == 0


# ---------------------------------------------------------------------------
# Buildings
# ---------------------------------------------------------------------------


def test_buildings_related_scope_uses_own_organization_only(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_org = _organization(
        db_session,
        legal_name="Foreign Org",
    )

    allowed = _building(
        db_session,
        name="Alpha Allowed Building",
        organization_id=allowed_org.id,
    )
    _building(
        db_session,
        name="Bravo Foreign Building",
        organization_id=foreign_org.id,
    )
    _building(
        db_session,
        name="Charlie Legacy Null Building",
        organization_id=None,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_buildings_paginated(
        db_session,
        authorization=ctx,
    )

    assert total == 1
    assert [item.id for item in items] == [allowed.id]

    foreign_items, foreign_total = list_buildings_paginated(
        db_session,
        organization_id=foreign_org.id,
        authorization=ctx,
    )

    assert foreign_items == []
    assert foreign_total == 0


def test_buildings_all_and_unrestricted_see_legacy_null(
    db_session: Session,
) -> None:
    org = _organization(
        db_session,
        legal_name="Org",
    )

    normal = _building(
        db_session,
        name="Normal Building",
        organization_id=org.id,
    )
    legacy = _building(
        db_session,
        name="Legacy Building",
        organization_id=None,
    )

    unrestricted, unrestricted_total = (
        list_buildings_paginated(
            db_session,
            authorization=None,
        )
    )
    all_items, all_total = list_buildings_paginated(
        db_session,
        authorization=_context(
            has_all_scope=True,
        ),
    )

    assert unrestricted_total == 2
    assert all_total == 2
    assert {item.id for item in unrestricted} == {
        normal.id,
        legacy.id,
    }
    assert {item.id for item in all_items} == {
        normal.id,
        legacy.id,
    }


def test_building_search_cannot_broaden_related_scope(
    db_session: Session,
) -> None:
    allowed_org = _organization(
        db_session,
        legal_name="Allowed Org",
    )
    foreign_org = _organization(
        db_session,
        legal_name="Foreign Org",
    )

    _building(
        db_session,
        name="Foreign Search Match",
        organization_id=foreign_org.id,
    )
    _building(
        db_session,
        name="Allowed Different Name",
        organization_id=allowed_org.id,
    )

    ctx = _context(
        allowed_organization_ids={allowed_org.id}
    )

    items, total = list_buildings_paginated(
        db_session,
        q="Foreign Search Match",
        authorization=ctx,
    )

    assert items == []
    assert total == 0