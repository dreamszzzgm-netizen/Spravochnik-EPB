from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.modules.contracts.models import Contract

REQUIRED_READINESS_KEYS = (
    "tasks",
    "expertises",
    "documents",
    "conclusion_delivery",
)

UNAVAILABLE_CODES = {
    "tasks": "tasks_provider_unavailable",
    "expertises": "expertises_provider_unavailable",
    "documents": "documents_provider_unavailable",
    "conclusion_delivery": "conclusion_delivery_provider_unavailable",
}

UNAVAILABLE_DETAILS = {
    "tasks": "Проверка обязательных задач недоступна до подключения модуля задач",
    "expertises": "Проверка обязательных экспертиз недоступна до подключения модуля экспертиз",
    "documents": "Проверка обязательных документов недоступна до подключения модуля документов",
    "conclusion_delivery": "Проверка выдачи заключений заказчику пока недоступна",
}


@dataclass(frozen=True)
class CompletionBlocker:
    code: str
    detail: str


@dataclass(frozen=True)
class CompletionCheck:
    key: str
    passed: bool
    blockers: tuple[CompletionBlocker, ...]


@dataclass(frozen=True)
class CompletionReadiness:
    ready_to_complete: bool
    checks: tuple[CompletionCheck, ...]
    blockers: tuple[CompletionBlocker, ...]


class CompletionReadinessProvider(Protocol):
    key: str

    def check(self, db: Session, contract: Contract) -> CompletionCheck:
        raise NotImplementedError


@dataclass(frozen=True)
class UnavailableReadinessProvider:
    key: str

    def check(self, db: Session, contract: Contract) -> CompletionCheck:
        blocker = CompletionBlocker(
            code=UNAVAILABLE_CODES[self.key],
            detail=UNAVAILABLE_DETAILS[self.key],
        )
        return CompletionCheck(key=self.key, passed=False, blockers=(blocker,))


def unavailable_readiness_provider(key: str) -> CompletionReadinessProvider:
    if key not in UNAVAILABLE_CODES:
        raise ValueError(f"Unknown readiness provider key: {key}")
    return UnavailableReadinessProvider(key=key)


def default_readiness_providers() -> dict[str, CompletionReadinessProvider]:
    return {
        key: unavailable_readiness_provider(key)
        for key in REQUIRED_READINESS_KEYS
    }
