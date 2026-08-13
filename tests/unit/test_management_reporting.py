# ruff: noqa

from datetime import date

from app.modules.analytics.management import (
    ManagementInput,
    TaskSnapshot,
    build_management_summary,
)
from app.modules.contracts.enums import ContractStatus
from app.modules.tasks.enums import TaskStatus


def test_builds_management_summary_from_cp51_operational_data() -> None:
    today = date(2026, 8, 13)
    data = ManagementInput(
        organizations_total=12,
        contract_statuses=[
            ContractStatus.IN_PROGRESS,
            ContractStatus.SIGNED,
            ContractStatus.COMPLETED,
            ContractStatus.TERMINATED,
        ],
        tasks=[
            TaskSnapshot(TaskStatus.NEW, date(2026, 8, 12)),
            TaskSnapshot(TaskStatus.IN_PROGRESS, date(2026, 8, 20)),
            TaskSnapshot(TaskStatus.COMPLETED, date(2026, 8, 10)),
            TaskSnapshot(TaskStatus.CANCELLED, None),
        ],
    )

    summary = build_management_summary(data, today=today)

    assert summary.organizations_total == 12
    assert summary.contracts.total == 4
    assert summary.contracts.active == 2
    assert summary.contracts.completed == 1
    assert summary.contracts.terminated == 1
    assert summary.tasks.total == 4
    assert summary.tasks.new == 1
    assert summary.tasks.in_progress == 1
    assert summary.tasks.completed == 1
    assert summary.tasks.cancelled == 1
    assert summary.tasks.overdue == 1
    assert not summary.documents.source_available
    assert not summary.expertises.source_available
