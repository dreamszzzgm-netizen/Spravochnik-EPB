import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.enums import enum_values
from app.modules.organizations.enums import IdentifierType, OrganizationType


class ContactType(enum.StrEnum):
    DIRECTOR = "director"
    CHIEF_ENGINEER = "chief_engineer"
    PB_SPECIALIST = "pb_specialist"
    ACCOUNTANT = "accountant"
    OTHER = "other"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(OrganizationType, name="organization_type", values_callable=enum_values),
        nullable=False,
        default=OrganizationType.LEGAL_ENTITY,
    )
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    short_name: Mapped[str | None] = mapped_column(String(120))
    legal_address: Mapped[str | None] = mapped_column(String(500))
    actual_address: Mapped[str | None] = mapped_column(String(500))
    residence_address: Mapped[str | None] = mapped_column(String(500))
    director_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320))
    passport_series: Mapped[str | None] = mapped_column(String(16))
    passport_number: Mapped[str | None] = mapped_column(String(32))
    passport_issued_by: Mapped[str | None] = mapped_column(String(500))
    passport_issue_date: Mapped[date | None] = mapped_column(Date)
    passport_department_code: Mapped[str | None] = mapped_column(String(32))
    bank_name: Mapped[str | None] = mapped_column(String(255))
    bank_bik: Mapped[str | None] = mapped_column(String(20))
    bank_account: Mapped[str | None] = mapped_column(String(64))
    correspondent_account: Mapped[str | None] = mapped_column(String(64))
    comment: Mapped[str | None] = mapped_column(String)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OrganizationContact(Base):
    __tablename__ = "organization_contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_type: Mapped[ContactType] = mapped_column(
        Enum(
            ContactType,
            name="contact_type",
            values_callable=enum_values,
            create_constraint=False,
        ),
        nullable=False,
        default=ContactType.OTHER,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index(
            "uq_organization_contacts_primary",
            "organization_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )


class OrganizationIdentifier(Base):
    __tablename__ = "organization_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    identifier_type: Mapped[IdentifierType] = mapped_column(
        Enum(IdentifierType, name="identifier_type", values_callable=enum_values),
        nullable=False,
    )
    identifier_value: Mapped[str] = mapped_column(String(40), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "identifier_type", name="uq_org_identifier_type_per_org"
        ),
        UniqueConstraint("identifier_type", "identifier_value", name="uq_org_identifier_value"),
        Index(
            "uq_organization_identifiers_primary",
            "organization_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
    )
