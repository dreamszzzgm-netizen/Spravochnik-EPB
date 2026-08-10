import uuid
from datetime import UTC, datetime
from datetime import date as date_type

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.modules.identity.audit import write_audit
from app.modules.opo.enums import HazardClass
from app.modules.opo.models import OPO, OPOActivityType, OPOHazardSign
from app.modules.opo.repository import (
    get_activity_type,
    get_hazard_sign,
    get_opo,
    get_registration_number_count,
    list_opo_activity_types,
    list_opo_hazard_signs,
)
from app.modules.organizations.repository import get_organization


class OPONotFoundError(Exception):
    pass


class OPOConflictError(Exception):
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
        registration_date: date_type,
        owner_organization_id: uuid.UUID,
        operating_organization_id: uuid.UUID,
        hazard_sign_ids: list[uuid.UUID] | None = None,
        activity_type_ids: list[uuid.UUID] | None = None,
        comment: str | None = None,
    ) -> OPO:
        owner = get_organization(db, owner_organization_id)
        if owner is None:
            raise OPONotFoundError("Owner organization not found")
        if owner.deleted_at is not None:
            raise OPONotFoundError("Owner organization is deleted")

        operator = get_organization(db, operating_organization_id)
        if operator is None:
            raise OPONotFoundError("Operating organization not found")
        if operator.deleted_at is not None:
            raise OPONotFoundError("Operating organization is deleted")

        if get_registration_number_count(db, registration_number) > 0:
            raise OPOConflictError(
                f"OPO with registration number {registration_number} already exists"
            )

        hazard_sign_ids = hazard_sign_ids or []
        activity_type_ids = activity_type_ids or []

        for sign_id in hazard_sign_ids:
            if get_hazard_sign(db, sign_id) is None:
                raise OPONotFoundError(f"Hazard sign {sign_id} not found")

        for type_id in activity_type_ids:
            if get_activity_type(db, type_id) is None:
                raise OPONotFoundError(f"Activity type {type_id} not found")

        opo = OPO(
            name=name,
            registration_number=registration_number,
            hazard_class=hazard_class,
            address=address,
            registration_date=registration_date,
            owner_organization_id=owner_organization_id,
            operating_organization_id=operating_organization_id,
            comment=comment,
        )
        db.add(opo)
        db.flush()

        for sign_id in hazard_sign_ids:
            db.add(OPOHazardSign(opo_id=opo.id, hazard_sign_id=sign_id))
        for type_id in activity_type_ids:
            db.add(OPOActivityType(opo_id=opo.id, activity_type_id=type_id))

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

    def update_opo(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        opo: OPO,
        name: str | None = None,
        registration_number: str | None = None,
        hazard_class: HazardClass | None = None,
        address: str | None = None,
        registration_date: date_type | None = None,
        owner_organization_id: uuid.UUID | None = None,
        operating_organization_id: uuid.UUID | None = None,
        hazard_sign_ids: list[uuid.UUID] | None = None,
        activity_type_ids: list[uuid.UUID] | None = None,
        comment: str | None = None,
        comment_provided: bool = False,
    ) -> OPO:
        changed: list[str] = []

        if name is not None and name != opo.name:
            opo.name = name
            changed.append("name")

        if (
            registration_number is not None
            and registration_number != opo.registration_number
        ):
            if get_registration_number_count(db, registration_number) > 0:
                raise OPOConflictError(
                    f"OPO with registration number {registration_number} already exists"
                )
            opo.registration_number = registration_number
            changed.append("registration_number")

        if hazard_class is not None and hazard_class != opo.hazard_class:
            opo.hazard_class = hazard_class
            changed.append("hazard_class")

        if address is not None and address != opo.address:
            opo.address = address
            changed.append("address")

        if registration_date is not None and registration_date != opo.registration_date:
            opo.registration_date = registration_date
            changed.append("registration_date")

        if owner_organization_id is not None and owner_organization_id != opo.owner_organization_id:
            owner = get_organization(db, owner_organization_id)
            if owner is None:
                raise OPONotFoundError("Owner organization not found")
            if owner.deleted_at is not None:
                raise OPONotFoundError("Owner organization is deleted")
            opo.owner_organization_id = owner_organization_id
            changed.append("owner_organization_id")

        if (
            operating_organization_id is not None
            and operating_organization_id != opo.operating_organization_id
        ):
            operator = get_organization(db, operating_organization_id)
            if operator is None:
                raise OPONotFoundError("Operating organization not found")
            if operator.deleted_at is not None:
                raise OPONotFoundError("Operating organization is deleted")
            opo.operating_organization_id = operating_organization_id
            changed.append("operating_organization_id")

        if hazard_sign_ids is not None:
            for sign_id in hazard_sign_ids:
                if get_hazard_sign(db, sign_id) is None:
                    raise OPONotFoundError(f"Hazard sign {sign_id} not found")
            db.execute(
                sa_text(
                    "DELETE FROM opo_hazard_signs WHERE opo_id = :opo_id"
                ),
                {"opo_id": opo.id},
            )
            for sign_id in hazard_sign_ids:
                db.add(OPOHazardSign(opo_id=opo.id, hazard_sign_id=sign_id))
            changed.append("hazard_signs")

        if activity_type_ids is not None:
            for type_id in activity_type_ids:
                if get_activity_type(db, type_id) is None:
                    raise OPONotFoundError(f"Activity type {type_id} not found")
            db.execute(
                sa_text(
                    "DELETE FROM opo_activity_types WHERE opo_id = :opo_id"
                ),
                {"opo_id": opo.id},
            )
            for type_id in activity_type_ids:
                db.add(OPOActivityType(opo_id=opo.id, activity_type_id=type_id))
            changed.append("activity_types")

        if comment_provided and comment != opo.comment:
            opo.comment = comment
            changed.append("comment")

        if changed:
            write_audit(
                db,
                user_id=actor_id,
                action="opo.updated",
                entity_type="opo",
                entity_id=opo.id,
                summary=f"OPO {opo.name} updated",
                result="success",
                metadata={"changed_fields": changed},
            )
            db.commit()
            db.refresh(opo)
        return opo

    def delete_opo(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        opo: OPO,
    ) -> None:
        db.execute(
            sa_text("UPDATE technical_devices SET opo_id = NULL WHERE opo_id = :opo_id"),
            {"opo_id": opo.id},
        )
        db.execute(
            sa_text("UPDATE buildings SET opo_id = NULL WHERE opo_id = :opo_id"),
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

    def restore_opo(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        opo: OPO,
    ) -> None:
        opo.deleted_at = None
        write_audit(
            db,
            user_id=actor_id,
            action="opo.restored",
            entity_type="opo",
            entity_id=opo.id,
            summary=f"OPO {opo.name} restored",
            result="success",
        )
        db.commit()

    def get_opo_detail(self, db: Session, opo_id: uuid.UUID) -> OPO | None:
        opo = get_opo(db, opo_id)
        if opo is None:
            return None
        opo.hazard_signs = list_opo_hazard_signs(db, opo_id)
        opo.activity_types = list_opo_activity_types(db, opo_id)
        return opo
