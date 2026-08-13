# ruff: noqa: I001

import io
import zipfile

from app.modules.organizations.enums import IdentifierType, OrganizationType
from app.modules.organizations.importer import (
    UnsupportedImportFormatError,
    extract_local_import_text,
    parse_organization_requisites,
)
from app.modules.organizations.schemas import OrganizationCreate


def _office_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


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


def test_legal_form_validation_contract_is_available() -> None:
    from app.modules.organizations.service import validate_organization_legal_form

    assert callable(validate_organization_legal_form)


def test_local_file_import_extracts_txt_docx_and_xlsx() -> None:
    assert "ООО Тест" in extract_local_import_text(
        "card.txt", "text/plain", "ООО Тест\nИНН: 7701234567".encode("utf-8")
    )

    docx = _office_zip(
        {
            "word/document.xml": """<?xml version='1.0' encoding='UTF-8'?>
            <w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
              <w:body><w:p><w:r><w:t>ООО DOCX</w:t></w:r></w:p></w:body>
            </w:document>"""
        }
    )
    assert "ООО DOCX" in extract_local_import_text(
        "card.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx,
    )

    xlsx = _office_zip(
        {
            "xl/worksheets/sheet1.xml": """<?xml version='1.0' encoding='UTF-8'?>
            <worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>
              <sheetData><row>
                <c t='inlineStr'><is><t>ИНН</t></is></c>
                <c t='inlineStr'><is><t>7701234567</t></is></c>
              </row></sheetData>
            </worksheet>"""
        }
    )
    assert "ИНН: 7701234567" in extract_local_import_text(
        "card.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        xlsx,
    )


def test_local_file_import_rejects_unknown_format() -> None:
    try:
        extract_local_import_text("card.bin", "application/octet-stream", b"binary")
    except UnsupportedImportFormatError:
        return
    raise AssertionError("Unknown import format was accepted")
