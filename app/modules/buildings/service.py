import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.buildings.enums import BuildingType
from app.modules.buildings.models import Building
from app.modules.identity.audit import write_audit


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
