import logging
from io import BytesIO
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import PyPDF2

    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import openpyxl

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes as pdf_convert_from_bytes

    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def _create_confidence_info_for_text(text: str, confidence_per_word: float, file_type: str) -> Dict[str, Any]:
    """Создаёт структуру confidence_info, совместимую с backend."""
    tokens = (text or "").split()
    words_with_confidence = [{"word": token, "confidence": float(confidence_per_word)} for token in tokens]
    avg_confidence = confidence_per_word
    return {
        "confidence": avg_confidence,
        "text_length": len(text or ""),
        "file_type": file_type,
        "words": words_with_confidence,
    }


async def _call_ocr_service(image_bytes: bytes, filename: str, languages: str = "ru,en") -> Dict[str, Any]:
    """Вызов ocr-service (Surya) по URL из настроек (SVC_OCR_URL / http://ocr-service:8000)."""
    settings = get_settings()
    ocr_url = settings.ocr.url.rstrip("/")
    timeout = settings.ocr.timeout

    mime = "image/jpeg"
    lower = filename.lower()
    if lower.endswith(".png"):
        mime = "image/png"

    files = {"file": (filename, BytesIO(image_bytes), mime)}
    data = {"languages": languages}

    try:
        req_timeout = httpx.Timeout(timeout, connect=10.0, read=timeout, write=10.0)
        async with httpx.AsyncClient(timeout=req_timeout) as client:
            resp = await client.post(f"{ocr_url}/v1/ocr", files=files, data=data, headers={"Accept": "application/json"})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error("Ошибка OCR при обращении к %s: %s", ocr_url, e)
        raise


def extract_text_from_docx(file_data: bytes) -> str:
    if not DOCX_AVAILABLE:
        raise RuntimeError("python-docx не установлен")
    doc = docx.Document(BytesIO(file_data))
    parts = []
    for para in doc.paragraphs:
        parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


async def extract_text_from_pdf_bytes(file_data: bytes) -> Dict[str, Any]:
    """
    Извлечение текста из PDF: сначала текстовый слой (pdfplumber/PyPDF2),
    при его отсутствии — OCR по растрированным страницам (Surya).
    Встроенные в PDF картинки (рисунки, скриншоты) не извлекаются и не отправляются в OCR —
    индексируется только текст из текстового слоя и, для сканов, распознанный по страницам текст.
    """
    print(f"Извлекаем текст из PDF файла (размер: {len(file_data)} байт)")
    text = ""
    confidence_scores = []

    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(BytesIO(file_data)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text
                    if page_text.strip():
                        confidence_scores.append(95.0)
                    else:
                        confidence_scores.append(50.0)
            print(f"PDFPlumber успешно извлек {len(text)} символов")
        except Exception as e:
            print(f"Ошибка при извлечении текста с помощью pdfplumber: {e}")

    if (not text or not text.strip()) and PYPDF2_AVAILABLE:
        try:
            reader = PyPDF2.PdfReader(BytesIO(file_data))
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text
                if page_text.strip():
                    confidence_scores.append(85.0)
                else:
                    confidence_scores.append(40.0)
            print(f"PyPDF2 успешно извлек {len(text)} символов")
        except Exception as e2:
            print(f"Ошибка при извлечении текста с помощью PyPDF2: {e2}")

    # Если текст не извлечён (сканированный PDF), пробуем OCR через Surya
    if (not text or not text.strip()) and PDF2IMAGE_AVAILABLE and PIL_AVAILABLE:
        print("PDF не содержит текста, возможно это сканированный документ. Пробуем OCR через Surya...")
        try:
            images = pdf_convert_from_bytes(file_data, dpi=300)
            print(f"PDF конвертирован в {len(images)} изображений для OCR")

            ocr_text = ""
            ocr_confidence_scores = []
            for i, image in enumerate(images):
                print(f"Обрабатываем страницу {i+1}/{len(images)} с помощью Surya OCR...")
                buf = BytesIO()
                image.save(buf, format="PNG")
                buf.seek(0)
                page_image_data = buf.getvalue()

                result = await _call_ocr_service(page_image_data, f"page_{i+1}.png", languages="ru,en")

                if result.get("success"):
                    page_text = result.get("text", "")
                    page_conf = result.get("confidence", 50.0)
                    ocr_text += f"\n--- Страница {i+1} ---\n{page_text}\n"
                    ocr_confidence_scores.append(page_conf)
                else:
                    print(f"OCR ошибка для страницы {i+1}: {result.get('error', 'Unknown error')}")
                    ocr_confidence_scores.append(50.0)

            if ocr_text.strip():
                text = ocr_text
                confidence_scores = ocr_confidence_scores
                print(f"Surya OCR успешно извлек {len(text)} символов из {len(images)} страниц")
            else:
                print("Surya OCR не смог извлечь текст из PDF")
        except Exception as e:
            print(f"Не удалось применить OCR к PDF: {e}")

    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
    confidence_per_word = 100.0 if avg_confidence > 90.0 else avg_confidence
    confidence_info = _create_confidence_info_for_text(text or "", confidence_per_word, "pdf")
    confidence_info["pages_processed"] = len(confidence_scores)

    return {"text": text or "", "confidence_info": confidence_info}


def extract_text_from_xlsx(file_data: bytes) -> str:
    if not OPENPYXL_AVAILABLE:
        raise RuntimeError("openpyxl не установлен")
    workbook = openpyxl.load_workbook(BytesIO(file_data), data_only=True)
    parts = []
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        parts.append(f"Лист: {sheet_name}")
        for row in sheet.iter_rows():
            row_vals = [str(c.value) for c in row if c.value is not None]
            if row_vals:
                parts.append("\t".join(row_vals))
    return "\n".join(parts)


def extract_text_from_txt(file_data: bytes) -> str:
    for enc in ("utf-8", "cp1251", "latin-1", "koi8-r"):
        try:
            return file_data.decode(enc)
        except UnicodeDecodeError:
            continue
    return file_data.decode("utf-8", errors="replace")


async def extract_text_from_image_bytes(file_data: bytes) -> Dict[str, Any]:
    """Извлечение текста из изображения (OCR). Вызов идёт в ocr-service (Surya)."""
    print(f"Извлекаем текст из изображения с помощью Surya OCR (размер: {len(file_data)} байт)")
    if not PIL_AVAILABLE:
        result_text = "[Изображение. Для распознавания текста требуется Pillow и доступ к ocr-service.]"
        return {
            "text": result_text,
            "confidence_info": _create_confidence_info_for_text(result_text, 0.0, "image"),
        }

    img = Image.open(BytesIO(file_data)).convert("RGB")
    filename = "image.jpg"
    if img.format:
        filename = f"image.{img.format.lower()}"

    print(f"DEBUG: Изображение открыто, формат: {img.format}, размер: {img.size}")

    # Увеличиваем маленькие изображения, как в backend
    min_side = 1024
    w, h = img.size
    if max(w, h) < min_side and max(w, h) > 0:
        scale = min_side / max(w, h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        print(f"DEBUG: Изображение увеличено для OCR: {w}x{h} -> {new_w}x{new_h}")

    buf = BytesIO()
    img.save(buf, format="PNG")
    image_to_send = buf.getvalue()

    try:
        result = await _call_ocr_service(image_to_send, filename, languages="ru,en")
    except Exception as e:
        print(f"Ошибка OCR: {e}")
        return {
            "text": "",
            "confidence_info": {
                "confidence": 0.0,
                "text_length": 0,
                "file_type": "image",
                "ocr_available": False,
                "error": str(e),
                "words": [],
            },
        }

    if not result.get("success"):
        error_msg = result.get("error", "Неизвестная ошибка")
        print(f"Surya OCR вернул ошибку: {error_msg}")
        return {
            "text": "",
            "confidence_info": {
                "confidence": 0.0,
                "text_length": 0,
                "file_type": "image",
                "ocr_available": False,
                "error": error_msg,
                "words": [],
            },
        }

    text = result.get("text", "") or ""
    words = result.get("words", []) or []
    avg_confidence = float(result.get("confidence", 0.0) or 0.0)

    if not text.strip():
        print("Surya OCR не смог извлечь текст из изображения (текст пустой)")
        return {
            "text": "",
            "confidence_info": {
                "confidence": 0.0,
                "text_length": 0,
                "file_type": "image",
                "ocr_available": False,
                "words": [],
            },
        }

    print(f"Surya OCR успешно извлек {len(text)} символов, {len(words)} слов, средняя уверенность: {avg_confidence:.2f}%")

    confidence_info = {
        "confidence": avg_confidence,
        "text_length": len(text),
        "file_type": "image",
        "ocr_available": True,
        "words": words,
    }
    return {"text": text, "confidence_info": confidence_info}


async def parse_document(file_data: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """
    По расширению файла выбираем парсер и возвращаем структуру:
    {"text": str, "confidence_info": dict}
    """
    name = (filename or "").lower()
    # Корректно извлекаем только сам суффикс (".docx", ".pdf" и т.п.)
    dot = name.rfind(".")
    ext = name[dot:] if dot != -1 else ""
    if ext == ".docx":
        if not DOCX_AVAILABLE:
            return None
        text = extract_text_from_docx(file_data)
        return {
            "text": text,
            "confidence_info": _create_confidence_info_for_text(text, 100.0, "docx"),
        }
    if ext == ".pdf":
        return await extract_text_from_pdf_bytes(file_data)
    if ext in (".xlsx", ".xls"):
        if not OPENPYXL_AVAILABLE:
            return None
        text = extract_text_from_xlsx(file_data)
        return {
            "text": text,
            "confidence_info": _create_confidence_info_for_text(text, 100.0, "excel"),
        }
    if ext == ".txt":
        text = extract_text_from_txt(file_data)
        return {
            "text": text,
            "confidence_info": _create_confidence_info_for_text(text, 100.0, "txt"),
        }
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        return await extract_text_from_image_bytes(file_data)
    return None
