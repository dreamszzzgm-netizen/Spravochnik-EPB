import uuid
from dataclasses import dataclass
from datetime import date

from app.modules.contracts.enums import ContractStatus
from app.modules.documents.control import DocumentStatus
from app.modules.tasks.enums import TaskStatus


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    status: TaskStatus
    due_date: date | None


@dataclass(frozen=True, slots=True)
class DocumentIssue:
    organization_id: uuid.UUID
    organization_name: str
    document_type: str
    document_title: str
    status: DocumentStatus
    expires_at: date | None = None
    days_left: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentControlSummary:
    source_available: bool
    total: int = 0
    expired: int = 0
    expiring_14: int = 0
    expiring_40: int = 0
    missing: int = 0
    no_expiry: int = 0
    valid: int = 0
    issues: tuple[DocumentIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class ManagementInput:
    organizations_total: int
    contract_statuses: list[ContractStatus]
    tasks: list[TaskSnapshot]
    documents: DocumentControlSummary


@dataclass(frozen=True, slots=True)
class ContractSummary:
    total: int
    active: int
    completed: int
    terminated: int


@dataclass(frozen=True, slots=True)
class TaskSummary:
    total: int
    new: int
    in_progress: int
    completed: int
    cancelled: int
    overdue: int


@dataclass(frozen=True, slots=True)
class SourceSummary:
    source_available: bool


@dataclass(frozen=True, slots=True)
class ManagementSummary:
    organizations_total: int
    contracts: ContractSummary
    tasks: TaskSummary
    documents: DocumentControlSummary
    expertises: SourceSummary


def build_management_summary(data: ManagementInput, *, today: date) -> ManagementSummary:
    active_contract_statuses = {ContractStatus.SIGNED, ContractStatus.IN_PROGRESS}
    contracts = ContractSummary(
        total=len(data.contract_statuses),
        active=sum(status in active_contract_statuses for status in data.contract_statuses),
        completed=data.contract_statuses.count(ContractStatus.COMPLETED),
        terminated=data.contract_statuses.count(ContractStatus.TERMINATED),
    )

    active_task_statuses = {TaskStatus.NEW, TaskStatus.IN_PROGRESS}
    tasks = TaskSummary(
        total=len(data.tasks),
        new=sum(task.status is TaskStatus.NEW for task in data.tasks),
        in_progress=sum(task.status is TaskStatus.IN_PROGRESS for task in data.tasks),
        completed=sum(task.status is TaskStatus.COMPLETED for task in data.tasks),
        cancelled=sum(task.status is TaskStatus.CANCELLED for task in data.tasks),
        overdue=sum(
            task.status in active_task_statuses
            and task.due_date is not None
            and task.due_date < today
            for task in data.tasks
        ),
    )

    return ManagementSummary(
        organizations_total=data.organizations_total,
        contracts=contracts,
        tasks=tasks,
        documents=data.documents,
        expertises=SourceSummary(source_available=False),
    )
