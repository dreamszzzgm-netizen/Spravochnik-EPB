import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.custom_fields.models import (
    CustomFieldDefinition,
    CustomFieldType,
    CustomFieldValue,
)
from app.modules.identity.audit import write_audit


class CustomFieldConflictError(Exception):
    pass


class CustomFieldNotFoundError(Exception):
    pass


class CustomFieldService:
    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def create_definition(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        code: str,
        name: str,
        entity_type: str,
        field_type: str,
    ) -> CustomFieldDefinition:
        definition = CustomFieldDefinition(
            code=code,
            name=name,
            entity_type=entity_type,
            field_type=CustomFieldType(field_type),
        )
        db.add(definition)
        db.flush()
        write_audit(
            db,
            user_id=actor_id,
            action="custom_field_definition.created",
            entity_type="custom_field_definition",
            entity_id=definition.id,
            summary=f"Custom field definition {code} created",
            result="success",
        )
        db.commit()
        return definition

    def set_value(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        field_definition_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
        value: str,
    ) -> CustomFieldValue:
        definition = db.get(CustomFieldDefinition, field_definition_id)
        if definition is None:
            raise CustomFieldNotFoundError(
                f"Custom field definition {field_definition_id} not found"
            )

        field_value = (
            db.query(CustomFieldValue)
            .filter_by(
                field_definition_id=field_definition_id,
                entity_type=entity_type,
                entity_id=entity_id,
            )
            .first()
        )

        if field_value is not None:
            raise CustomFieldConflictError(
                f"Value already exists for field {field_definition_id} on {entity_type} {entity_id}"
            )

        field_value = CustomFieldValue(
            field_definition_id=field_definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
            value_text=value,
        )
        db.add(field_value)
        try:
            db.flush()
        except IntegrityError as err:
            db.rollback()
            raise CustomFieldConflictError(
                f"Value already exists for field {field_definition_id} on {entity_type} {entity_id}"
            ) from err

        write_audit(
            db,
            user_id=actor_id,
            action="custom_field_value.set",
            entity_type="custom_field_value",
            entity_id=field_value.id,
            summary=f"Custom field value set for {entity_type} {entity_id}",
            result="success",
        )
        db.commit()
        return field_value
