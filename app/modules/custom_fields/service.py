import uuid
from datetime import UTC, datetime
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import select
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


class CustomFieldValidationError(Exception):
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

    def list_definitions(
        self, db: Session, *, entity_type: str | None = None
    ) -> list[CustomFieldDefinition]:
        stmt = select(CustomFieldDefinition)
        if entity_type is not None:
            stmt = stmt.where(CustomFieldDefinition.entity_type == entity_type)
        return list(db.scalars(stmt.order_by(CustomFieldDefinition.code)))

    def get_values(
        self,
        db: Session,
        *,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> list[CustomFieldValue]:
        return list(
            db.scalars(
                select(CustomFieldValue)
                .where(
                    CustomFieldValue.entity_type == entity_type,
                    CustomFieldValue.entity_id == entity_id,
                )
                .order_by(CustomFieldValue.field_definition_id)
            )
        )

    def _validate_value(
        self,
        db: Session,
        definition: CustomFieldDefinition,
        value: str,
    ) -> str | Decimal | date_type | bool:
        field_type = definition.field_type
        if field_type == CustomFieldType.TEXT:
            return value
        if field_type == CustomFieldType.NUMBER:
            try:
                return Decimal(value)
            except Exception as exc:
                raise CustomFieldValidationError(
                    f"Value '{value}' is not a valid number for field {definition.code}"
                ) from exc
        if field_type == CustomFieldType.DATE:
            try:
                return date_type.fromisoformat(value)
            except Exception as exc:
                raise CustomFieldValidationError(
                    f"Value '{value}' is not a valid date (YYYY-MM-DD) for field {definition.code}"
                ) from exc
        if field_type == CustomFieldType.BOOLEAN:
            if value.lower() in ("true", "1", "yes"):
                return True
            if value.lower() in ("false", "0", "no"):
                return False
            raise CustomFieldValidationError(
                f"Value '{value}' is not a valid boolean for field {definition.code}"
            )
        raise CustomFieldValidationError(f"Unknown field type {field_type}")

    def _write_typed_value(self, field_value: CustomFieldValue, value: object) -> None:
        if isinstance(value, Decimal):
            field_value.value_number = value
        elif isinstance(value, date_type):
            field_value.value_date = value
        elif isinstance(value, bool):
            field_value.value_boolean = value
        else:
            field_value.value_text = str(value)

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

        if definition.entity_type != entity_type:
            raise CustomFieldValidationError(
                f"Field definition {definition.code} does not apply to entity type {entity_type}"
            )

        typed_value = self._validate_value(db, definition, value)

        existing = db.scalar(
            select(CustomFieldValue).where(
                CustomFieldValue.field_definition_id == field_definition_id,
                CustomFieldValue.entity_type == entity_type,
                CustomFieldValue.entity_id == entity_id,
            )
        )

        if existing is not None:
            raise CustomFieldConflictError(
                f"Value already exists for field {field_definition_id} on {entity_type} {entity_id}"
            )

        field_value = CustomFieldValue(
            field_definition_id=field_definition_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        self._write_typed_value(field_value, typed_value)
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
            entity_id=field_definition_id,
            summary=f"Custom field value set for {entity_type} {entity_id}",
            result="success",
        )
        db.commit()
        return existing or field_value

    def clear_value(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID,
        field_definition_id: uuid.UUID,
        entity_type: str,
        entity_id: uuid.UUID,
    ) -> None:
        existing = db.scalar(
            select(CustomFieldValue).where(
                CustomFieldValue.field_definition_id == field_definition_id,
                CustomFieldValue.entity_type == entity_type,
                CustomFieldValue.entity_id == entity_id,
            )
        )
        if existing is None:
            raise CustomFieldNotFoundError("Custom field value not found")
        db.delete(existing)
        write_audit(
            db,
            user_id=actor_id,
            action="custom_field_value.cleared",
            entity_type="custom_field_value",
            entity_id=field_definition_id,
            summary=f"Custom field value cleared for {entity_type} {entity_id}",
            result="success",
        )
        db.commit()
