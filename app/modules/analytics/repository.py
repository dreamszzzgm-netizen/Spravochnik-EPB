from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.analytics.management import ManagementInput, TaskSnapshot
from app.modules.contracts.models import Contract
from app.modules.organizations.models import Organization
from app.modules.tasks.models import Task


def load_management_input(db: Session) -> ManagementInput:
    organizations_total = db.scalar(
        select(func.count()).select_from(Organization).where(Organization.deleted_at.is_(None))
    ) or 0
    contract_statuses = list(
        db.scalars(select(Contract.status).where(Contract.deleted_at.is_(None))).all()
    )
    task_rows = db.execute(
        select(Task.status, Task.due_date).where(Task.deleted_at.is_(None))
    ).all()
    return ManagementInput(
        organizations_total=organizations_total,
        contract_statuses=contract_statuses,
        tasks=[TaskSnapshot(status=status, due_date=due_date) for status, due_date in task_rows],
    )
