from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.smart_import import parse_organization_text


def test_parses_individual_entrepreneur_card_into_candidate() -> None:
    text = """
    Индивидуальный предприниматель Иванов Иван Иванович
    ИНН: 123456789012
    ОГРНИП: 321123456789012
    Место жительства: г. Москва, ул. Примерная, д. 10
    Паспорт: серия 4510 номер 123456
    Выдан: ОМВД России по г. Москве
    Дата выдачи: 12.03.2019
    Код подразделения: 770-001
    Телефон: +7 999 123-45-67
    Email: ivanov@example.ru
    БИК: 044525225
    Расчетный счет: 40802810123450000001
    Корреспондентский счет: 30101810400000000225
    """

    candidate = parse_organization_text(text)

    assert candidate.organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR
    assert candidate.legal_name == "Иванов Иван Иванович"
    assert candidate.identifiers[IdentifierType.INN] == "123456789012"
    assert candidate.identifiers[IdentifierType.OGRNIP] == "321123456789012"
    assert candidate.residence_address == "г. Москва, ул. Примерная, д. 10"
    assert candidate.passport_series == "4510"
    assert candidate.passport_number == "123456"
    assert candidate.passport_issued_by == "ОМВД России по г. Москве"
    assert candidate.passport_issue_date == "2019-03-12"
    assert candidate.passport_department_code == "770-001"
    assert candidate.phone == "+7 999 123-45-67"
    assert candidate.email == "ivanov@example.ru"
    assert candidate.bank_bik == "044525225"
    assert candidate.bank_account == "40802810123450000001"
    assert candidate.correspondent_account == "30101810400000000225"


def test_parses_legal_entity_card_without_ip_fields() -> None:
    text = """
    Полное наименование: Общество с ограниченной ответственностью «Альфа»
    Сокращенное наименование: ООО «Альфа»
    ИНН: 7701234567
    КПП: 770101001
    ОГРН: 1027700123456
    Юридический адрес: г. Москва, ул. Тестовая, д. 1
    Генеральный директор: Петров Петр Петрович
    Email: office@alpha.ru
    """

    candidate = parse_organization_text(text)

    assert candidate.organization_type is OrganizationType.LEGAL_ENTITY
    assert candidate.legal_name == "Общество с ограниченной ответственностью «Альфа»"
    assert candidate.short_name == "ООО «Альфа»"
    assert candidate.identifiers[IdentifierType.INN] == "7701234567"
    assert candidate.identifiers[IdentifierType.KPP] == "770101001"
    assert candidate.identifiers[IdentifierType.OGRN] == "1027700123456"
    assert IdentifierType.OGRNIP not in candidate.identifiers
    assert candidate.legal_address == "г. Москва, ул. Тестовая, д. 1"
    assert candidate.director_name == "Петров Петр Петрович"
    assert candidate.residence_address is None
    assert candidate.passport_number is None


def test_candidate_reports_low_confidence_fields_instead_of_persisting() -> None:
    candidate = parse_organization_text("ИНН: 7701234567")

    assert candidate.identifiers[IdentifierType.INN] == "7701234567"
    assert candidate.requires_review
    assert candidate.organization_type is None
    assert candidate.warnings
