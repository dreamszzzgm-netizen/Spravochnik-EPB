import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.enums import enum_values
from app.modules.expertises.enums import ExpertiseParticipantRole, ExpertiseStatus


class Expertise(Base):
    __tablename__ = "expertises"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expertise_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertise_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[ExpertiseStatus] = mapped_column(
        Enum(ExpertiseStatus, name="expertise_status", values_callable=enum_values),
        nullable=False,
        default=ExpertiseStatus.PREPARATION,
        index=True,
    )
    internal_number: Mapped[str | None] = mapped_column(String(120))
    responsible_expert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ExpertiseSubject(Base):
    __tablename__ = "expertise_subjects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expertise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertises.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    technical_device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("technical_devices.id", ondelete="RESTRICT"),
        nullable=True,
    )
    building_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "(technical_device_id IS NOT NULL AND building_id IS NULL) OR "
            "(technical_device_id IS NULL AND building_id IS NOT NULL)",
            name="ck_expertise_subjects_single_subject",
        ),
    )


class ExpertiseContractItem(Base):
    __tablename__ = "expertise_contract_items"

    expertise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertises.id", ondelete="CASCADE"),
        primary_key=True,
    )
    contract_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_items.id", ondelete="RESTRICT"),
        primary_key=True,
    )


class ExpertiseParticipant(Base):
    __tablename__ = "expertise_participants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expertise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    participation_role: Mapped[ExpertiseParticipantRole] = mapped_column(
        Enum(
            ExpertiseParticipantRole,
            name="expertise_participation_role",
            values_callable=enum_values,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "expertise_id",
            "employee_id",
            "participation_role",
            name="uq_expertise_participants_employee_role",
        ),
    )


class ExpertiseStatusHistory(Base):
    __tablename__ = "expertise_status_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expertise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("expertises.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[ExpertiseStatus | None] = mapped_column(
        Enum(ExpertiseStatus, name="expertise_status", values_callable=enum_values),
        nullable=True,
    )
    to_status: Mapped[ExpertiseStatus] = mapped_column(
        Enum(ExpertiseStatus, name="expertise_status", values_callable=enum_values),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(Text)
