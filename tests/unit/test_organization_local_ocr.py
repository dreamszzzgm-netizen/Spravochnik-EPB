import io

import pytest
from PIL import Image
from pytesseract import TesseractNotFoundError

from app.modules.organizations import local_ocr
from app.modules.organizations.importer import extract_local_import_text


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_png_import_uses_local_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        local_ocr.pytesseract,
        "image_to_string",
        lambda *args, **kwargs: "ИП Иванов Иван Иванович\nИНН: 770123456789",
    )

    text = extract_local_import_text("card.png", "image/png", _png_bytes())

    assert "ИП Иванов Иван Иванович" in text
    assert "770123456789" in text


def test_local_ocr_fails_closed_when_tesseract_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args, **kwargs):
        raise TesseractNotFoundError()

    monkeypatch.setattr(local_ocr.pytesseract, "image_to_string", missing)

    with pytest.raises(local_ocr.LocalOcrUnavailableError):
        local_ocr.extract_image_text(_png_bytes())


def test_scanned_pdf_import_uses_local_pdf_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def extract_text(self) -> None:
            return None

    class FakeReader:
        pages = [FakePage()]

    monkeypatch.setattr(
        "app.modules.organizations.importer.PdfReader",
        lambda *args, **kwargs: FakeReader(),
    )
    monkeypatch.setattr(
        local_ocr,
        "extract_scanned_pdf_text",
        lambda raw, max_pages=20: "ООО Скан\nИНН: 7701234567",
    )

    text = extract_local_import_text("scan.pdf", "application/pdf", b"fake-pdf")

    assert "ООО Скан" in text
    assert "7701234567" in text
