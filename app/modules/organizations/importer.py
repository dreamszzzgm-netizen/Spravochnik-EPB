import io
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

from app.modules.organizations import local_ocr
from app.modules.organizations.enums import IdentifierType, OrganizationType

_MAX_OFFICE_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
_MAX_PDF_PAGES = 20
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


class UnsupportedImportFormatError(ValueError):
    pass


class InvalidImportFileError(ValueError):
    pass


class LocalOcrUnavailableError(RuntimeError):
    pass


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


def extract_local_import_text(filename: str, content_type: str | None, raw: bytes) -> str:
    """Extract text locally; never fall back to an external service for organization PII."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt" or (not suffix and content_type == "text/plain"):
        return _decode_text(raw)
    if suffix == ".docx":
        return _extract_docx(raw)
    if suffix == ".xlsx":
        return _extract_xlsx(raw)
    if suffix == ".pdf":
        return _extract_pdf_text(raw)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return _extract_image_text(raw)
    raise UnsupportedImportFormatError("Неподдерживаемый формат файла реквизитов")


def _decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidImportFileError("TXT должен быть в UTF-8") from exc


def _open_office_zip(raw: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise InvalidImportFileError("Файл Office повреждён") from exc
    expanded = sum(info.file_size for info in archive.infolist())
    if expanded > _MAX_OFFICE_UNCOMPRESSED_BYTES:
        archive.close()
        raise InvalidImportFileError("Распакованный файл Office превышает безопасный лимит")
    return archive


def _xml(archive: zipfile.ZipFile, path: str) -> ElementTree.Element:
    try:
        data = archive.read(path)
    except KeyError as exc:
        raise InvalidImportFileError(f"В документе отсутствует {path}") from exc
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise InvalidImportFileError(f"Повреждён XML {path}") from exc


def _element_text(element: ElementTree.Element, namespace: str) -> str:
    return "".join(
        node.text or ""
        for node in element.iter(f"{{{namespace}}}t")
        if (node.text or "").strip()
    ).strip()


def _extract_docx(raw: bytes) -> str:
    with _open_office_zip(raw) as archive:
        root = _xml(archive, "word/document.xml")
    body = root.find(f"{{{_WORD_NS}}}body")
    if body is None:
        raise InvalidImportFileError("DOCX не содержит body")

    lines: list[str] = []
    paragraph_tag = f"{{{_WORD_NS}}}p"
    table_tag = f"{{{_WORD_NS}}}tbl"
    row_tag = f"{{{_WORD_NS}}}tr"
    cell_tag = f"{{{_WORD_NS}}}tc"
    for child in body:
        if child.tag == paragraph_tag:
            text = _element_text(child, _WORD_NS)
            if text:
                lines.append(text)
        elif child.tag == table_tag:
            for row in child.iter(row_tag):
                cells = [
                    text
                    for cell in row.findall(cell_tag)
                    if (text := _element_text(cell, _WORD_NS))
                ]
                if len(cells) == 2:
                    lines.append(f"{cells[0]}: {cells[1]}")
                elif cells:
                    lines.append(" ".join(cells))
    return "\n".join(lines)


def _extract_xlsx(raw: bytes) -> str:
    with _open_office_zip(raw) as archive:
        shared = _xlsx_shared_strings(archive)
        worksheets = sorted(
            info.filename
            for info in archive.infolist()
            if info.filename.startswith("xl/worksheets/") and info.filename.endswith(".xml")
        )
        if not worksheets:
            raise InvalidImportFileError("XLSX не содержит листов")
        lines: list[str] = []
        for path in worksheets:
            root = _xml(archive, path)
            for row in root.findall(f".//{{{_SHEET_NS}}}row"):
                values = [
                    value
                    for cell in row.findall(f"{{{_SHEET_NS}}}c")
                    if (value := _xlsx_cell_value(cell, shared))
                ]
                if len(values) == 2:
                    lines.append(f"{values[0]}: {values[1]}")
                elif values:
                    lines.append(" ".join(values))
        return "\n".join(lines)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    except ElementTree.ParseError as exc:
        raise InvalidImportFileError("Повреждены sharedStrings XLSX") from exc
    return [_element_text(node, _SHEET_NS) for node in root.findall(f"{{{_SHEET_NS}}}si")]


def _xlsx_cell_value(cell: ElementTree.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return _element_text(cell, _SHEET_NS)
    value_node = cell.find(f"{{{_SHEET_NS}}}v")
    value = (value_node.text or "").strip() if value_node is not None else ""
    if not value:
        return ""
    if cell_type != "s":
        return value
    try:
        return shared[int(value)]
    except (ValueError, IndexError) as exc:
        raise InvalidImportFileError("Повреждена ссылка shared string в XLSX") from exc


def _extract_pdf_text(raw: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        raise InvalidImportFileError("PDF повреждён") from exc
    if len(reader.pages) > _MAX_PDF_PAGES:
        raise InvalidImportFileError(f"PDF содержит больше {_MAX_PDF_PAGES} страниц")
    text = "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    if text:
        return text
    try:
        return local_ocr.extract_scanned_pdf_text(raw, max_pages=_MAX_PDF_PAGES)
    except local_ocr.LocalOcrUnavailableError as exc:
        raise LocalOcrUnavailableError(str(exc)) from exc
    except local_ocr.InvalidOcrInputError as exc:
        raise InvalidImportFileError(str(exc)) from exc


def _extract_image_text(raw: bytes) -> str:
    try:
        return local_ocr.extract_image_text(raw)
    except local_ocr.LocalOcrUnavailableError as exc:
        raise LocalOcrUnavailableError(str(exc)) from exc
    except local_ocr.InvalidOcrInputError as exc:
        raise InvalidImportFileError(str(exc)) from exc
