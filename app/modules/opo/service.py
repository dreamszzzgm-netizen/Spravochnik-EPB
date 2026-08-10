import uuid
from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO
from app.modules.organizations.repository import get_organization


class OPONotFoundError(Exception):
    pass


class OPOService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def create_opo(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        name: str,
        registration_number: str,
        hazard_class: HazardClass,
        address: str,
        registration_date: date_type | None = None,
        owner_organization_id: uuid.UUID,
        operating_organization_id: uuid.UUID,
    ) -> OPO:
        if get_organization(db, owner_organization_id) is None:
            raise OPONotFoundError("Owner organization not found")
        if get_organization(db, operating_organization_id) is None:
            raise OPONotFoundError("Operating organization not found")

        opo = OPO(
            name=name,
            registration_number=registration_number,
            hazard_class=hazard_class,
            address=address,
            registration_date=registration_date or date_type.today(),
            owner_organization_id=owner_organization_id,
            operating_organization_id=operating_organization_id,
        )
        db.add(opo)
        db.flush()
        write_audit(
            db,
            user_id=actor_id,
            action="opo.created",
            entity_type="opo",
            entity_id=opo.id,
            summary=f"OPO {name} created",
            result="success",
        )
        db.commit()
        return opo

    def delete_opo(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        opo: OPO,
    ) -> None:
        db.execute(
            text("UPDATE technical_devices SET opo_id = NULL WHERE opo_id = :opo_id"),
            {"opo_id": opo.id},
        )
        db.execute(
            text("UPDATE buildings SET opo_id = NULL WHERE opo_id = :opo_id"),
            {"opo_id": opo.id},
        )
        opo.deleted_at = self._now()
        write_audit(
            db,
            user_id=actor_id,
            action="opo.deleted",
            entity_type="opo",
            entity_id=opo.id,
            summary=f"OPO {opo.name} deleted",
            result="success",
        )
        db.commit()
