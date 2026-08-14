# ruff: noqa: I001

import pytest

from app.modules.documents.policy import DocumentUploadPolicyError, validate_document_upload


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("doc.pdf", "application/pdf"),
        (
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        (
            "table.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ),
        ("photo.jpg", "image/jpeg"),
        ("scan.png", "image/png"),
        ("scan.tiff", "image/tiff"),
        ("legacy.doc", "application/msword"),
        ("legacy.xls", "application/vnd.ms-excel"),
        ("REPORT.PDF", "application/octet-stream"),
        ("scan.tif", None),
    ],
)
def test_allowed_document_uploads(name: str, mime: str | None) -> None:
    validate_document_upload(name, mime)


@pytest.mark.parametrize(
    "name",
    [
        "payload.exe",
        "library.dll",
        "run.bat",
        "run.cmd",
        "run.ps1",
        "script.js",
        "page.html",
        "unknown.bin",
        "no-extension",
        "../report.pdf",
        r"folder\report.pdf",
        "bad\x00name.pdf",
    ],
)
def test_disallowed_document_filenames_are_rejected(name: str) -> None:
    with pytest.raises(DocumentUploadPolicyError):
        validate_document_upload(name, "application/octet-stream")


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("report.pdf", "text/html"),
        ("photo.jpg", "application/javascript"),
        ("table.xlsx", "application/x-msdownload"),
    ],
)
def test_known_mime_mismatch_is_rejected(name: str, mime: str) -> None:
    with pytest.raises(DocumentUploadPolicyError):
        validate_document_upload(name, mime)
