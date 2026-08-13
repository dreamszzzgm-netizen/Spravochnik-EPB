import re
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.organizations.enums import IdentifierType, OrganizationType


class OrganizationImportCandidate(BaseModel):
    organization_type: OrganizationType | None = None
    legal_name: str | None = None
    short_name: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    residence_address: str | None = None
    director_name: str | None = None
    phone: str | None = None
    email: str | None = None
    identifiers: dict[IdentifierType, str] = Field(default_factory=dict)
    passport_series: str | None = None
    passport_number: str | None = None
    passport_issued_by: str | None = None
    passport_issue_date: str | None = None
    passport_department_code: str | None = None
    bank_name: str | None = None
    bank_bik: str | None = None
    bank_account: str | None = None
    correspondent_account: str | None = None
    requires_review: bool = True
    warnings: list[str] = Field(default_factory=list)


def _line_value(text: str, *labels: str) -> str | None:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?im)^\s*(?:{label_pattern})\s*:\s*(?P<value>.+?)\s*$",
        text,
    )
    return match.group("value").strip() if match else None


def _identifier(text: str, label: str) -> str | None:
    value = _line_value(text, label)
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def _detect_organization_type(text: str) -> OrganizationType | None:
    if re.search(r"(?i)индивидуальн(?:ый|ого)\s+предпринимател", text):
        return OrganizationType.INDIVIDUAL_ENTREPRENEUR
    if re.search(r"(?im)^\s*ОГРНИП\s*:", text):
        return OrganizationType.INDIVIDUAL_ENTREPRENEUR
    if re.search(r"(?im)^\s*(?:ОГРН|КПП|Полное\s+наименование)\s*:", text):
        return OrganizationType.LEGAL_ENTITY
    return None


def _ip_name(text: str) -> str | None:
    match = re.search(
        r"(?im)^\s*Индивидуальный\s+предприниматель\s+(?P<name>.+?)\s*$",
        text,
    )
    return match.group("name").strip() if match else None


def _passport_parts(text: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"(?im)^\s*Паспорт\s*:\s*(?:серия\s*)?"
        r"(?P<series>\d{2}\s?\d{2}|\d{4})\s*"
        r"(?:номер\s*)?(?P<number>\d{6})\s*$",
        text,
    )
    if match is None:
        return None, None
    series = re.sub(r"\s", "", match.group("series"))
    return series, match.group("number")


def _date_value(text: str, *labels: str) -> str | None:
    value = _line_value(text, *labels)
    if value is None:
        return None
    for date_format in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue
    return value


def parse_organization_text(text: str) -> OrganizationImportCandidate:
    """Extract a local, review-only organization candidate from plain text."""
    organization_type = _detect_organization_type(text)
    identifiers: dict[IdentifierType, str] = {}
    for identifier_type, label in (
        (IdentifierType.INN, "ИНН"),
        (IdentifierType.KPP, "КПП"),
        (IdentifierType.OGRN, "ОГРН"),
        (IdentifierType.OGRNIP, "ОГРНИП"),
    ):
        value = _identifier(text, label)
        if value:
            identifiers[identifier_type] = value

    passport_series, passport_number = _passport_parts(text)
    legal_name = _line_value(text, "Полное наименование")
    if organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR:
        legal_name = _ip_name(text) or legal_name

    warnings: list[str] = []
    if organization_type is None:
        warnings.append("Не удалось уверенно определить тип организации.")
    if legal_name is None:
        warnings.append("Не удалось определить наименование организации или ФИО ИП.")

    return OrganizationImportCandidate(
        organization_type=organization_type,
        legal_name=legal_name,
        short_name=_line_value(text, "Сокращенное наименование", "Сокращённое наименование"),
        legal_address=_line_value(text, "Юридический адрес"),
        actual_address=_line_value(text, "Фактический адрес"),
        residence_address=_line_value(text, "Место жительства"),
        director_name=_line_value(text, "Генеральный директор", "Директор", "Руководитель"),
        phone=_line_value(text, "Телефон"),
        email=_line_value(text, "Email", "E-mail", "Электронная почта"),
        identifiers=identifiers,
        passport_series=passport_series,
        passport_number=passport_number,
        passport_issued_by=_line_value(text, "Выдан", "Кем выдан"),
        passport_issue_date=_date_value(text, "Дата выдачи"),
        passport_department_code=_line_value(text, "Код подразделения"),
        bank_name=_line_value(text, "Банк", "Наименование банка"),
        bank_bik=_identifier(text, "БИК"),
        bank_account=_identifier(text, "Расчетный счет") or _identifier(text, "Расчётный счет"),
        correspondent_account=(
            _identifier(text, "Корреспондентский счет")
            or _identifier(text, "Корреспондентский счёт")
        ),
        warnings=warnings,
    )
