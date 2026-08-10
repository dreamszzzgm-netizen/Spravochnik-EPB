import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.technical_devices.enums import TechnicalDeviceType
from app.modules.technical_devices.models import TechnicalDevice


class TechnicalDeviceNotFoundError(Exception):
    pass


class TechnicalDeviceService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def create_technical_device(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        name: str,
        device_type: TechnicalDeviceType,
        opo_id: uuid.UUID | None = None,
        serial_number: str | None = None,
    ) -> TechnicalDevice:
        device = TechnicalDevice(
            name=name,
            device_type=device_type,
            serial_number=serial_number,
            opo_id=opo_id,
        )
        db.add(device)
        db.flush()
        write_audit(
            db,
            user_id=actor_id,
            action="technical_device.created",
            entity_type="technical_device",
            entity_id=device.id,
            summary=f"Technical device {name} created",
            result="success",
        )
        db.commit()
        return device

    def delete_technical_device(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        device: TechnicalDevice,
    ) -> None:
        device.deleted_at = self._now()
        write_audit(
            db,
            user_id=actor_id,
            action="technical_device.deleted",
            entity_type="technical_device",
            entity_id=device.id,
            summary=f"Technical device {device.name} deleted",
            result="success",
        )
        db.commit()
