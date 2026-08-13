from datetime import date, timedelta

from app.modules.analytics import repository
from app.modules.analytics.management import (
    DocumentControlSummary,
    ManagementInput,
    TaskSnapshot,
    build_management_summary,
)
from app.modules.contracts.enums import ContractStatus
from app.modules.tasks.enums import TaskStatus


def test_management_summary_uses_live_contract_and_task_states() -> None:
    today = date(2026, 8, 13)
    summary = build_management_summary(
        ManagementInput(
            organizations_total=3,
            contract_statuses=[
                ContractStatus.SIGNED,
                ContractStatus.IN_PROGRESS,
                ContractStatus.COMPLETED,
                ContractStatus.TERMINATED,
            ],
            tasks=[
                TaskSnapshot(TaskStatus.NEW, today - timedelta(days=1)),
                TaskSnapshot(TaskStatus.IN_PROGRESS, today + timedelta(days=1)),
                TaskSnapshot(TaskStatus.COMPLETED, today - timedelta(days=5)),
            ],
            documents=DocumentControlSummary(source_available=False),
        ),
        today=today,
    )

    assert summary.organizations_total == 3
    assert summary.contracts.total == 4
    assert summary.contracts.active == 2
    assert summary.contracts.completed == 1
    assert summary.tasks.total == 3
    assert summary.tasks.overdue == 1
    assert not summary.documents.source_available


def test_document_control_is_safe_before_tables_exist(monkeypatch) -> None:
    monkeypatch.setattr(repository, "_document_tables_available", lambda db: False)

    result = repository.load_document_control(object(), today=date(2026, 8, 13))  # type: ignore[arg-type]

    assert not result.source_available
    assert result.total == 0
    assert result.issues == ()
