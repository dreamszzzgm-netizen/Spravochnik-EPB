# ruff: noqa: I001

from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.importer import parse_organization_requisites
from app.modules.organizations.schemas import OrganizationCreate


def test_ip_schema_accepts_residence_and_passport_fields() -> None:
    payload = OrganizationCreate(
        legal_name="ИП Иванов Иван Иванович",
        organization_type=OrganizationType.INDIVIDUAL_ENTREPRENEUR,
        residence_address="г. Москва, ул. Примерная, д. 1",
        passport_details="45 01 123456, выдан ОВД Примерный 01.02.2010",
    )

    assert payload.residence_address == "г. Москва, ул. Примерная, д. 1"
    assert payload.passport_details.startswith("45 01 123456")


def test_parser_extracts_individual_entrepreneur_requisites() -> None:
    candidate = parse_organization_requisites(
        """
        Индивидуальный предприниматель Иванов Иван Иванович
        ИНН: 770123456789
        ОГРНИП: 326770000123456
        Место жительства: г. Москва, ул. Примерная, д. 1
        Паспорт: 45 01 123456, выдан ОВД Примерный 01.02.2010
        Телефон: +7 (999) 123-45-67
        Email: ivanov@example.ru
        """
    )

    assert candidate.organization_type is OrganizationType.INDIVIDUAL_ENTREPRENEUR
    assert candidate.legal_name == "ИП Иванов Иван Иванович"
    assert candidate.residence_address == "г. Москва, ул. Примерная, д. 1"
    assert candidate.passport_details == "45 01 123456, выдан ОВД Примерный 01.02.2010"
    assert candidate.phone == "+7 (999) 123-45-67"
    assert candidate.email == "ivanov@example.ru"
    assert candidate.identifiers == {
        IdentifierType.INN: "770123456789",
        IdentifierType.OGRNIP: "326770000123456",
    }


def test_parser_extracts_legal_entity_requisites_without_ip_fields() -> None:
    candidate = parse_organization_requisites(
        """
        Общество с ограниченной ответственностью «ПромЭксперт»
        Краткое наименование: ООО «ПромЭксперт»
        ИНН 7701234567
        КПП 770101001
        ОГРН 1027700123456
        Юридический адрес: 105005, г. Москва, ул. Бауманская, д. 1
        Фактический адрес: 105005, г. Москва, ул. Бауманская, д. 2
        Руководитель: Петров Петр Петрович
        """
    )

    assert candidate.organization_type is OrganizationType.LEGAL_ENTITY
    assert candidate.legal_name == "Общество с ограниченной ответственностью «ПромЭксперт»"
    assert candidate.short_name == "ООО «ПромЭксперт»"
    assert candidate.legal_address == "105005, г. Москва, ул. Бауманская, д. 1"
    assert candidate.actual_address == "105005, г. Москва, ул. Бауманская, д. 2"
    assert candidate.director_name == "Петров Петр Петрович"
    assert candidate.residence_address is None
    assert candidate.passport_details is None
    assert candidate.identifiers == {
        IdentifierType.INN: "7701234567",
        IdentifierType.KPP: "770101001",
        IdentifierType.OGRN: "1027700123456",
    }
