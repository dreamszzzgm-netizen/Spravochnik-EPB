import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.enums import enum_values
from app.modules.tasks.enums import TaskPriority, TaskStatus


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "(source_workflow_template_version_id IS NULL "
            "AND source_workflow_task_template_id IS NULL) "
            "OR (source_workflow_template_version_id IS NOT NULL "
            "AND source_workflow_task_template_id IS NOT NULL)",
            name="ck_tasks_workflow_source_pair",
        ),
        ForeignKeyConstraint(
            ["source_workflow_task_template_id", "source_workflow_template_version_id"],
            ["workflow_task_templates.id", "workflow_task_templates.workflow_template_version_id"],
            name="fk_tasks_workflow_source",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    creator_employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority", values_callable=enum_values),
        nullable=False,
        default=TaskPriority.NORMAL,
        index=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", values_callable=enum_values),
        nullable=False,
        default=TaskStatus.NEW,
        index=True,
    )
    is_personal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_workflow_template_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    source_workflow_task_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class TaskAssignee(Base):
    __tablename__ = "task_assignees"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )


class TaskOrganization(Base):
    __tablename__ = "task_organizations"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskContract(Base):
    __tablename__ = "task_contracts"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskContractItem(Base):
    __tablename__ = "task_contract_items"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    contract_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contract_items.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskTechnicalDevice(Base):
    __tablename__ = "task_technical_devices"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    technical_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("technical_devices.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskBuilding(Base):
    __tablename__ = "task_buildings"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskOPO(Base):
    __tablename__ = "task_opos"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    opo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opo.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
