import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.buildings.service import (
    BuildingOrganizationError,
    BuildingService,
)
from app.modules.organizations.models import Organization, OrganizationType
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice
from app.modules.technical_devices.service import (
    TechnicalDeviceNotFoundError,
    TechnicalDeviceService,
)


@pytest.mark.integration
class TestBuildingServiceOrganizationInvariant:
    """Regression tests for BuildingService organization_id invariant."""

    def _create_org(self, db_session: Session, name: str, short: str) -> Organization:
        org = Organization(
            legal_name=name,
            short_name=short,
            organization_type=OrganizationType.LEGAL_ENTITY,
        )
        db_session.add(org)
        db_session.flush()
        return org

    def test_update_building_rejects_explicit_none_organization_id(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call with organization_id=None, organization_id_provided=True
        must reject and not clear existing organization_id."""
        org = self._create_org(db_session, "Test Org", "TEST")

        building = Building(
            name="Test Building",
            building_type=BuildingType.OTHER,
            organization_id=org.id,
        )
        db_session.add(building)
        db_session.flush()

        service = BuildingService()
        actor_id = uuid.UUID(test_user["id"])

        # Attempt to set organization_id to None explicitly
        with pytest.raises(BuildingOrganizationError) as exc_info:
            service.update_building(
                db_session,
                actor_id=actor_id,
                building=building,
                organization_id=None,
                organization_id_provided=True,
            )

        assert "cannot be set to None" in str(exc_info.value)

        # Verify organization_id was NOT changed
        db_session.refresh(building)
        assert building.organization_id == org.id

    def test_update_building_allows_changing_organization_id(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call with valid new organization_id must succeed."""
        org_a = self._create_org(db_session, "Org A", "ORGA")
        org_b = self._create_org(db_session, "Org B", "ORGB")

        building = Building(
            name="Test Building",
            building_type=BuildingType.OTHER,
            organization_id=org_a.id,
        )
        db_session.add(building)
        db_session.flush()

        service = BuildingService()
        actor_id = uuid.UUID(test_user["id"])

        # Change to org_b
        result = service.update_building(
            db_session,
            actor_id=actor_id,
            building=building,
            organization_id=org_b.id,
            organization_id_provided=True,
        )

        assert result.organization_id == org_b.id

    def test_update_building_preserves_organization_when_omitted(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call without organization_id must preserve existing value."""
        org = self._create_org(db_session, "Test Org", "TEST")

        building = Building(
            name="Test Building",
            building_type=BuildingType.OTHER,
            organization_id=org.id,
        )
        db_session.add(building)
        db_session.flush()

        service = BuildingService()
        actor_id = uuid.UUID(test_user["id"])

        # Update without providing organization_id
        result = service.update_building(
            db_session,
            actor_id=actor_id,
            building=building,
            name="Renamed",
        )

        assert result.organization_id == org.id
        assert result.name == "Renamed"


@pytest.mark.integration
class TestTechnicalDeviceServiceOrganizationInvariant:
    """Regression tests for TechnicalDeviceService organization_id invariant."""

    def _create_org(self, db_session: Session, name: str, short: str) -> Organization:
        org = Organization(
            legal_name=name,
            short_name=short,
            organization_type=OrganizationType.LEGAL_ENTITY,
        )
        db_session.add(org)
        db_session.flush()
        return org

    def test_update_technical_device_rejects_explicit_none_organization_id(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call with organization_id=None, organization_id_provided=True
        must reject and not clear existing organization_id."""
        org = self._create_org(db_session, "Test Org", "TEST")

        device = TechnicalDevice(
            name="Test Device",
            device_type=TechnicalDeviceType.OTHER,
            organization_id=org.id,
        )
        db_session.add(device)
        db_session.flush()

        service = TechnicalDeviceService()
        actor_id = uuid.UUID(test_user["id"])

        # Attempt to set organization_id to None explicitly
        # Current implementation: get_organization(db, None) returns None,
        # raises "Organization not found"
        with pytest.raises(TechnicalDeviceNotFoundError) as exc_info:
            service.update_technical_device(
                db_session,
                actor_id=actor_id,
                device=device,
                organization_id=None,
                organization_id_provided=True,
            )

        assert "Organization not found" in str(exc_info.value)

        # Verify organization_id was NOT changed
        db_session.refresh(device)
        assert device.organization_id == org.id

    def test_update_technical_device_allows_changing_organization_id(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call with valid new organization_id must succeed."""
        org_a = self._create_org(db_session, "Org A", "ORGA")
        org_b = self._create_org(db_session, "Org B", "ORGB")

        device = TechnicalDevice(
            name="Test Device",
            device_type=TechnicalDeviceType.OTHER,
            organization_id=org_a.id,
        )
        db_session.add(device)
        db_session.flush()

        service = TechnicalDeviceService()
        actor_id = uuid.UUID(test_user["id"])

        result = service.update_technical_device(
            db_session,
            actor_id=actor_id,
            device=device,
            organization_id=org_b.id,
            organization_id_provided=True,
        )

        assert result.organization_id == org_b.id

    def test_update_technical_device_preserves_organization_when_omitted(
        self, db_session: Session, test_user: dict
    ) -> None:
        """Direct service call without organization_id must preserve existing value."""
        org = self._create_org(db_session, "Test Org", "TEST")

        device = TechnicalDevice(
            name="Test Device",
            device_type=TechnicalDeviceType.OTHER,
            organization_id=org.id,
        )
        db_session.add(device)
        db_session.flush()

        service = TechnicalDeviceService()
        actor_id = uuid.UUID(test_user["id"])

        result = service.update_technical_device(
            db_session,
            actor_id=actor_id,
            device=device,
            name="Renamed",
        )

        assert result.organization_id == org.id
        assert result.name == "Renamed"