from pathlib import Path


class DocumentUploadPolicyError(ValueError):
    pass


_ALLOWED_MIME_TYPES: dict[str, frozenset[str]] = {
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword"}),
    ".docx": frozenset(
        {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    ),
    ".xls": frozenset({"application/vnd.ms-excel"}),
    ".xlsx": frozenset(
        {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".png": frozenset({"image/png"}),
    ".tif": frozenset({"image/tiff"}),
    ".tiff": frozenset({"image/tiff"}),
}
_GENERIC_MIME = "application/octet-stream"


def _normalized_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized or None


def validate_document_upload(filename: str, content_type: str | None) -> None:
    if not filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise DocumentUploadPolicyError("invalid document filename")

    suffix = Path(filename).suffix.lower()
    allowed_mimes = _ALLOWED_MIME_TYPES.get(suffix)
    if allowed_mimes is None:
        raise DocumentUploadPolicyError("document file type is not allowed")

    normalized_content_type = _normalized_content_type(content_type)
    if normalized_content_type is None or normalized_content_type == _GENERIC_MIME:
        return
    if normalized_content_type not in allowed_mimes:
        raise DocumentUploadPolicyError("document MIME type does not match file extension")
