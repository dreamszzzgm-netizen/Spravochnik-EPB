from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.modules.organizations.import_files import (
    UnsupportedImportFormatError,
    extract_local_import_text,
)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_extracts_utf8_text_file() -> None:
    raw = "ИНН: 123456789012\nОГРНИП: 321123456789012".encode()

    text = extract_local_import_text("card.txt", "text/plain", raw)

    assert "ИНН: 123456789012" in text
    assert "ОГРНИП: 321123456789012" in text


def test_extracts_docx_paragraphs_and_table_cells() -> None:
    raw = _zip_bytes(
        {
            "word/document.xml": """
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                  <w:body>
                    <w:p><w:r><w:t>Индивидуальный предприниматель Иванов Иван Иванович</w:t></w:r></w:p>
                    <w:tbl><w:tr>
                      <w:tc><w:p><w:r><w:t>ИНН</w:t></w:r></w:p></w:tc>
                      <w:tc><w:p><w:r><w:t>123456789012</w:t></w:r></w:p></w:tc>
                    </w:tr></w:tbl>
                  </w:body>
                </w:document>
            """,
        }
    )

    text = extract_local_import_text(
        "card.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        raw,
    )

    assert "Индивидуальный предприниматель Иванов Иван Иванович" in text
    assert "ИНН: 123456789012" in text


def test_extracts_xlsx_two_column_rows_as_requisite_pairs() -> None:
    raw = _zip_bytes(
        {
            "xl/sharedStrings.xml": """
                <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                  <si><t>ИНН</t></si>
                  <si><t>ОГРНИП</t></si>
                </sst>
            """,
            "xl/worksheets/sheet1.xml": """
                <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                  <sheetData>
                    <row r="1">
                      <c r="A1" t="s"><v>0</v></c>
                      <c r="B1"><v>123456789012</v></c>
                    </row>
                    <row r="2">
                      <c r="A2" t="s"><v>1</v></c>
                      <c r="B2"><v>321123456789012</v></c>
                    </row>
                  </sheetData>
                </worksheet>
            """,
        }
    )

    text = extract_local_import_text(
        "card.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        raw,
    )

    assert "ИНН: 123456789012" in text
    assert "ОГРНИП: 321123456789012" in text


def test_rejects_pdf_or_image_until_local_handler_is_available() -> None:
    with pytest.raises(UnsupportedImportFormatError):
        extract_local_import_text("card.pdf", "application/pdf", b"%PDF")

    with pytest.raises(UnsupportedImportFormatError):
        extract_local_import_text("passport.jpg", "image/jpeg", b"jpeg")
