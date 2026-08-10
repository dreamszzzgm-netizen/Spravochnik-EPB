import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.opo.repository import get_opo
from app.modules.organizations.repository import get_organization
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
        organization_id: uuid.UUID,
        opo_id: uuid.UUID | None = None,
        serial_number: str | None = None,
    ) -> TechnicalDevice:
        org = get_organization(db, organization_id)
        if org is None:
            raise TechnicalDeviceNotFoundError("Organization not found")
        if org.deleted_at is not None:
            raise TechnicalDeviceNotFoundError("Organization is deleted")

        if opo_id is not None:
            opo = get_opo(db, opo_id)
            if opo is None:
                raise TechnicalDeviceNotFoundError("OPO not found")
            if opo.deleted_at is not None:
                raise TechnicalDeviceNotFoundError("OPO is deleted")

        device = TechnicalDevice(
            name=name,
            device_type=device_type,
            serial_number=serial_number,
            opo_id=opo_id,
            organization_id=organization_id,
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

    def update_technical_device(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        device: TechnicalDevice,
        name: str | None = None,
        device_type: TechnicalDeviceType | None = None,
        serial_number: str | None = None,
        serial_number_provided: bool = False,
        opo_id: uuid.UUID | None = None,
        opo_id_provided: bool = False,
        organization_id: uuid.UUID | None = None,
    ) -> TechnicalDevice:
        changed: list[str] = []

        if name is not None and name != device.name:
            device.name = name
            changed.append("name")
        if device_type is not None and device_type != device.device_type:
            device.device_type = device_type
            changed.append("device_type")
        if serial_number_provided and serial_number != device.serial_number:
            device.serial_number = serial_number or None
            changed.append("serial_number")

        if opo_id_provided and opo_id != device.opo_id:
            if opo_id is not None:
                opo = get_opo(db, opo_id)
                if opo is None:
                    raise TechnicalDeviceNotFoundError("OPO not found")
                if opo.deleted_at is not None:
                    raise TechnicalDeviceNotFoundError("OPO is deleted")
            device.opo_id = opo_id
            changed.append("opo_id")

        if organization_id is not None and organization_id != device.organization_id:
            org = get_organization(db, organization_id)
            if org is None:
                raise TechnicalDeviceNotFoundError("Organization not found")
            if org.deleted_at is not None:
                raise TechnicalDeviceNotFoundError("Organization is deleted")
            device.organization_id = organization_id
            changed.append("organization_id")

        if changed:
            write_audit(
                db,
                user_id=actor_id,
                action="technical_device.updated",
                entity_type="technical_device",
                entity_id=device.id,
                summary=f"Technical device {device.name} updated",
                result="success",
                metadata={"changed_fields": changed},
            )
            db.commit()
            db.refresh(device)
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

    def restore_technical_device(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        device: TechnicalDevice,
    ) -> None:
        device.deleted_at = None
        write_audit(
            db,
            user_id=actor_id,
            action="technical_device.restored",
            entity_type="technical_device",
            entity_id=device.id,
            summary=f"Technical device {device.name} restored",
            result="success",
        )
        db.commit()
