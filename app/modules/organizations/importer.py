import re
from dataclasses import dataclass, field

from app.modules.organizations.enums import IdentifierType, OrganizationType


@dataclass(slots=True)
class OrganizationImportCandidate:
    organization_type: OrganizationType = OrganizationType.LEGAL_ENTITY
    legal_name: str | None = None
    short_name: str | None = None
    legal_address: str | None = None
    actual_address: str | None = None
    residence_address: str | None = None
    director_name: str | None = None
    passport_details: str | None = None
    phone: str | None = None
    email: str | None = None
    identifiers: dict[IdentifierType, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _value_after_label(line: str, *labels: str) -> str | None:
    lowered = line.casefold()
    for label in labels:
        normalized = label.casefold()
        if lowered.startswith(normalized):
            value = line[len(label) :].lstrip(" :—-\t")
            return value.strip() or None
    return None


def _identifier(lines: list[str], label: str, length: int) -> str | None:
    pattern = re.compile(rf"\b{re.escape(label)}\s*[:№-]?\s*(\d{{{length}}})\b", re.IGNORECASE)
    for line in lines:
        match = pattern.search(line)
        if match:
            return match.group(1)
    return None


def parse_organization_requisites(text: str) -> OrganizationImportCandidate:
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    candidate = OrganizationImportCandidate()
    if not lines:
        candidate.warnings.append("Не удалось найти реквизиты в пустом тексте.")
        return candidate

    first = lines[0]
    first_folded = first.casefold()
    if first_folded.startswith("индивидуальный предприниматель"):
        candidate.organization_type = OrganizationType.INDIVIDUAL_ENTREPRENEUR
        name = first[len("Индивидуальный предприниматель") :].strip(" :—-")
        candidate.legal_name = f"ИП {name}" if name else first
    elif re.match(r"^ип\s+", first, re.IGNORECASE):
        candidate.organization_type = OrganizationType.INDIVIDUAL_ENTREPRENEUR
        candidate.legal_name = first
    else:
        candidate.legal_name = first

    for line in lines[1:]:
        value = _value_after_label(line, "Краткое наименование")
        if value is not None:
            candidate.short_name = value
            continue
        value = _value_after_label(line, "Юридический адрес")
        if value is not None:
            candidate.legal_address = value
            continue
        value = _value_after_label(line, "Фактический адрес")
        if value is not None:
            candidate.actual_address = value
            continue
        value = _value_after_label(line, "Место жительства")
        if value is not None:
            candidate.residence_address = value
            continue
        value = _value_after_label(line, "Руководитель", "Директор")
        if value is not None:
            candidate.director_name = value
            continue
        value = _value_after_label(line, "Паспортные данные", "Паспорт")
        if value is not None:
            candidate.passport_details = value
            continue
        value = _value_after_label(line, "Телефон")
        if value is not None:
            candidate.phone = value
            continue
        value = _value_after_label(line, "Email", "E-mail", "Электронная почта")
        if value is not None:
            candidate.email = value

    ogrnip = _identifier(lines, "ОГРНИП", 15)
    ogrn = _identifier(lines, "ОГРН", 13)
    kpp = _identifier(lines, "КПП", 9)
    inn_12 = _identifier(lines, "ИНН", 12)
    inn_10 = _identifier(lines, "ИНН", 10)

    if inn_12 or inn_10:
        candidate.identifiers[IdentifierType.INN] = inn_12 or inn_10 or ""
    if candidate.organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR:
        if ogrnip:
            candidate.identifiers[IdentifierType.OGRNIP] = ogrnip
    else:
        if kpp:
            candidate.identifiers[IdentifierType.KPP] = kpp
        if ogrn:
            candidate.identifiers[IdentifierType.OGRN] = ogrn

    if candidate.legal_name is None:
        candidate.warnings.append("Полное наименование не распознано.")
    return candidate
