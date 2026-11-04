import io

from PIL import Image


def extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF bytes using pypdf. Returns empty string if none."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""

    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t:
                parts.append(t)
        return "\n".join(parts).strip()
    except Exception:
        return ""


TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"tesseract",
]


def _configure_tesseract():
    """Point pytesseract to the Tesseract binary if available."""
    import shutil

    import pytesseract
    for path in TESSERACT_PATHS:
        if path == "tesseract":
            if shutil.which("tesseract"):
                break
            continue
        import os
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            break


def ocr_image(data: bytes, lang="eng") -> str:
    """OCR an image (PNG/JPEG bytes) via Tesseract. Returns recognized text."""
    try:
        import pytesseract
        _configure_tesseract()
    except ImportError:
        return ""

    try:
        img = Image.open(io.BytesIO(data))
        text = pytesseract.image_to_string(img, lang=lang)
        return text.strip()
    except Exception:
        return ""


def ocr_pdf(data: bytes, lang="eng") -> str:
    """OCR a PDF: rasterize each page to an image and run Tesseract."""
    try:
        import pypdf
        import pytesseract
        _configure_tesseract()
    except ImportError:
        return ""

    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            # Rasterize via page handle (pypdf alone can't render);
            # fall back gracefully if rendering dependencies are missing.
            try:
                from pdf2image import convert_from_bytes
            except ImportError:
                return ""
            images = convert_from_bytes(data, first_page=page.page_number + 1,
                                        last_page=page.page_number + 1, dpi=200)
            for img in images:
                text = pytesseract.image_to_string(img, lang=lang)
                if text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    except Exception:
        return ""


def extract_from_bytes(data: bytes, filename: str, use_ocr: bool = False,
                       lang="eng") -> str:
    """High-level: extract text from an uploaded file (pdf) or OCR an image."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        text = extract_pdf_text(data)
        if not text.strip() and use_ocr:
            text = ocr_pdf(data, lang=lang)
        return text
    # Treat as image for OCR (png/jpg/jpeg/webp/bmp)
    if use_ocr:
        return ocr_image(data, lang=lang)
    return ""