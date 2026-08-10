import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.identity.audit import write_audit
from app.modules.opo.repository import get_opo


class BuildingNotFoundError(Exception):
    pass


class BuildingService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def create_building(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        name: str,
        building_type: BuildingType,
        opo_id: uuid.UUID | None = None,
    ) -> Building:
        if opo_id is not None:
            opo = get_opo(db, opo_id)
            if opo is None:
                raise BuildingNotFoundError("OPO not found")
            if opo.deleted_at is not None:
                raise BuildingNotFoundError("OPO is deleted")

        building = Building(
            name=name,
            building_type=building_type,
            opo_id=opo_id,
        )
        db.add(building)
        db.flush()
        write_audit(
            db,
            user_id=actor_id,
            action="building.created",
            entity_type="building",
            entity_id=building.id,
            summary=f"Building {name} created",
            result="success",
        )
        db.commit()
        return building

    def update_building(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        building: Building,
        name: str | None = None,
        building_type: BuildingType | None = None,
        opo_id: uuid.UUID | None = None,
    ) -> Building:
        changed: list[str] = []

        if name is not None and name != building.name:
            building.name = name
            changed.append("name")
        if building_type is not None and building_type != building.building_type:
            building.building_type = building_type
            changed.append("building_type")

        if opo_id != building.opo_id:
            if opo_id is not None:
                opo = get_opo(db, opo_id)
                if opo is None:
                    raise BuildingNotFoundError("OPO not found")
                if opo.deleted_at is not None:
                    raise BuildingNotFoundError("OPO is deleted")
            building.opo_id = opo_id
            changed.append("opo_id")

        if changed:
            write_audit(
                db,
                user_id=actor_id,
                action="building.updated",
                entity_type="building",
                entity_id=building.id,
                summary=f"Building {building.name} updated",
                result="success",
                metadata={"changed_fields": changed},
            )
            db.commit()
            db.refresh(building)
        return building

    def delete_building(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        building: Building,
    ) -> None:
        building.deleted_at = self._now()
        write_audit(
            db,
            user_id=actor_id,
            action="building.deleted",
            entity_type="building",
            entity_id=building.id,
            summary=f"Building {building.name} deleted",
            result="success",
        )
        db.commit()

    def restore_building(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        building: Building,
    ) -> None:
        building.deleted_at = None
        write_audit(
            db,
            user_id=actor_id,
            action="building.restored",
            entity_type="building",
            entity_id=building.id,
            summary=f"Building {building.name} restored",
            result="success",
        )
        db.commit()
