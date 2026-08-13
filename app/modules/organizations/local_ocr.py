import io
import os

import pypdfium2 as pdfium
import pytesseract
from PIL import Image, UnidentifiedImageError
from pytesseract import TesseractError, TesseractNotFoundError


class LocalOcrUnavailableError(RuntimeError):
    pass


class InvalidOcrInputError(ValueError):
    pass


def _configure_tesseract() -> None:
    configured = os.getenv("TESSERACT_CMD")
    if configured:
        pytesseract.pytesseract.tesseract_cmd = configured


def _ocr_image(image: Image.Image) -> str:
    _configure_tesseract()
    try:
        text = pytesseract.image_to_string(
            image.convert("RGB"),
            lang=os.getenv("TESSERACT_LANG", "rus+eng"),
            config="--psm 6",
            timeout=30,
        ).strip()
    except TesseractNotFoundError as exc:
        raise LocalOcrUnavailableError(
            "Локальный Tesseract OCR не установлен или не найден"
        ) from exc
    except TesseractError as exc:
        raise InvalidOcrInputError("Локальный OCR завершился ошибкой") from exc
    except RuntimeError as exc:
        raise InvalidOcrInputError("Локальный OCR превысил лимит времени") from exc
    if not text:
        raise InvalidOcrInputError("Локальный OCR не распознал текст")
    return text


def extract_image_text(raw: bytes) -> str:
    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            return _ocr_image(image)
    except UnidentifiedImageError as exc:
        raise InvalidOcrInputError("Файл изображения повреждён или не поддерживается") from exc


def extract_scanned_pdf_text(raw: bytes, *, max_pages: int = 20) -> str:
    try:
        document = pdfium.PdfDocument(raw)
    except Exception as exc:
        raise InvalidOcrInputError("PDF повреждён") from exc

    try:
        page_count = len(document)
        if page_count == 0:
            raise InvalidOcrInputError("PDF не содержит страниц")
        if page_count > max_pages:
            raise InvalidOcrInputError(f"PDF содержит больше {max_pages} страниц")

        pages: list[str] = []
        for index in range(page_count):
            page = document[index]
            bitmap = None
            try:
                bitmap = page.render(scale=300 / 72, grayscale=True)
                pages.append(_ocr_image(bitmap.to_pil()))
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
        return "\n".join(pages).strip()
    finally:
        document.close()
