import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree


class UnsupportedImportFormatError(ValueError):
    pass


class InvalidImportFileError(ValueError):
    pass


_MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024
_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def extract_local_import_text(
    filename: str,
    content_type: str | None,
    raw: bytes,
) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt" or (not suffix and content_type == "text/plain"):
        return _decode_text(raw)
    if suffix == ".docx":
        return _extract_docx(raw)
    if suffix == ".xlsx":
        return _extract_xlsx(raw)
    raise UnsupportedImportFormatError("Unsupported local import format")


def _decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidImportFileError("Text file must use UTF-8 encoding") from exc


def _open_office_zip(raw: bytes) -> zipfile.ZipFile:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise InvalidImportFileError("Office document is not a valid ZIP container") from exc

    total_size = sum(info.file_size for info in archive.infolist())
    if total_size > _MAX_UNCOMPRESSED_BYTES:
        archive.close()
        raise InvalidImportFileError("Office document expands beyond the local safety limit")
    return archive


def _xml_from_archive(archive: zipfile.ZipFile, path: str) -> ElementTree.Element:
    try:
        xml_bytes = archive.read(path)
    except KeyError as exc:
        raise InvalidImportFileError(f"Office document is missing {path}") from exc
    try:
        return ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as exc:
        raise InvalidImportFileError(f"Office document contains invalid XML in {path}") from exc


def _element_text(element: ElementTree.Element, namespace: str) -> str:
    parts = [
        node.text or ""
        for node in element.iter(f"{{{namespace}}}t")
        if (node.text or "").strip()
    ]
    return "".join(parts).strip()


def _extract_docx(raw: bytes) -> str:
    with _open_office_zip(raw) as archive:
        root = _xml_from_archive(archive, "word/document.xml")

    body = root.find(f"{{{_WORD_NS}}}body")
    if body is None:
        raise InvalidImportFileError("DOCX document has no body")

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
        shared_strings = _xlsx_shared_strings(archive)
        worksheet_paths = sorted(
            info.filename
            for info in archive.infolist()
            if info.filename.startswith("xl/worksheets/")
            and info.filename.endswith(".xml")
        )
        if not worksheet_paths:
            raise InvalidImportFileError("XLSX document has no worksheets")

        lines: list[str] = []
        for path in worksheet_paths:
            root = _xml_from_archive(archive, path)
            lines.extend(_xlsx_rows(root, shared_strings))
    return "\n".join(lines)


def _xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    except ElementTree.ParseError as exc:
        raise InvalidImportFileError("XLSX shared strings XML is invalid") from exc

    return [_element_text(item, _SHEET_NS) for item in root.findall(f"{{{_SHEET_NS}}}si")]


def _xlsx_rows(root: ElementTree.Element, shared_strings: list[str]) -> list[str]:
    lines: list[str] = []
    row_tag = f".//{{{_SHEET_NS}}}row"
    cell_tag = f"{{{_SHEET_NS}}}c"

    for row in root.findall(row_tag):
        values = [
            value
            for cell in row.findall(cell_tag)
            if (value := _xlsx_cell_value(cell, shared_strings))
        ]
        if len(values) == 2:
            lines.append(f"{values[0]}: {values[1]}")
        elif values:
            lines.append(" ".join(values))
    return lines


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
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
        index = int(value)
        return shared_strings[index]
    except (ValueError, IndexError) as exc:
        raise InvalidImportFileError("XLSX shared-string reference is invalid") from exc
