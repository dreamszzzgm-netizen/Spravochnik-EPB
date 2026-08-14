from app.modules.workflows.models import WorkflowTaskTemplate


def pytest_configure() -> None:
    assert WorkflowTaskTemplate.__tablename__ == "workflow_task_templates"
