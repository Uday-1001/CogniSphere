import gc
import logging
import os
import re
import threading
import warnings
from typing import Callable, List, Optional, Any

import pymupdf as fitz
import numpy as np
from langchain_core.documents import Document
from PIL import Image, ImageEnhance

try:
    from app.config.settings import settings
except ImportError:
    from ..config.settings import settings

try:
    # pyrefly: ignore [missing-import]
    import google.generativeai as genai
except ImportError:
    genai = None

for env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[env_var] = "1"

warnings.filterwarnings("ignore", message=".*pin_memory.*")
logger = logging.getLogger(__name__)

_thread_local = threading.local()


def unload_reader():
    if hasattr(_thread_local, "reader"):
        try:
            delattr(_thread_local, "reader")
            logger.info("Unloaded EasyOCR PyTorch reader from memory.")
        except Exception as e:
            logger.warning("Error unloading EasyOCR reader: %s", e)
    gc.collect()


def get_reader(languages: List[str]) -> Any:
    if not hasattr(_thread_local, "reader"):
        try:
            import torch
            import easyocr
            torch.set_num_threads(1)
            logger.info("Thread %s: initialising EasyOCR (langs=%s)...", threading.current_thread().name, languages)
            _thread_local.reader = easyocr.Reader(languages, gpu=False, verbose=False)
        except ImportError:
            raise ImportError("EasyOCR is not installed. Run: pip install easyocr")
    return _thread_local.reader


def page_to_image(page: fitz.Page, dpi: Optional[int] = None, max_px: Optional[int] = None) -> np.ndarray:
    target_dpi = dpi or settings.OCR_DPI
    target_max_px = max_px or settings.OCR_MAX_PX
    pixmap = page.get_pixmap(matrix=fitz.Matrix(target_dpi / 72, target_dpi / 72), alpha=False, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    w, h = image.size
    if max(w, h) > target_max_px:
        scale = target_max_px / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return np.array(ImageEnhance.Contrast(image).enhance(settings.OCR_CONTRAST_FACTOR))


def sort_into_reading_order(results: list) -> list:
    return sorted(
        results,
        key=lambda item: (round(min(pt[1] for pt in item[0]) / 15), min(pt[0] for pt in item[0]))
    )


def detect_section(text: str) -> Optional[str]:
    for line in (l.strip() for l in text.splitlines()):
        if line and len(line) < 80 and (
            (line.isupper() and len(line) > 3) or line.endswith(":") or re.match(r"^\d+[\.\/\)]\s+\w", line)
        ):
            return line
    return None


def page_to_pil(page: fitz.Page, dpi: Optional[int] = None, max_px: Optional[int] = None) -> Image.Image:
    target_dpi = dpi or settings.OCR_DPI
    target_max_px = max_px or settings.OCR_MAX_PX
    pixmap = page.get_pixmap(matrix=fitz.Matrix(target_dpi / 72, target_dpi / 72), alpha=False, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    w, h = image.size
    if max(w, h) > target_max_px:
        scale = target_max_px / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return ImageEnhance.Contrast(image).enhance(settings.OCR_CONTRAST_FACTOR)


class PDFOCRPipeline:
    SCANNED_CHAR_THRESHOLD = 10

    def __init__(
        self,
        dpi: Optional[int] = None,
        languages: Optional[List[str]] = None,
        char_threshold: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        self.dpi = dpi or settings.OCR_DPI
        self.languages = languages or settings.OCR_LANGUAGE.split(",")
        self.max_workers = getattr(settings, "OCR_MAX_WORKERS", 1) or 1
        if char_threshold is not None:
            self.SCANNED_CHAR_THRESHOLD = char_threshold

    def is_scanned(self, pdf_path: str) -> bool:
        try:
            with fitz.open(pdf_path) as pdf:
                total_chars = 0
                for page in pdf:
                    text = page.get_text()
                    if isinstance(text, str):
                        total_chars += len(text.strip())
                avg_chars = total_chars / max(len(pdf), 1)
                return avg_chars < self.SCANNED_CHAR_THRESHOLD
        except Exception as file_error:
            logger.warning("Could not read PDF text layer: %s — assuming scanned.", file_error)
            return True

    def process(
        self,
        pdf_path: str,
        filename: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Document]:
        documents: List[Document] = []
        try:
            with fitz.open(pdf_path) as pdf:
                total_pages = len(pdf)
                use_gemini = getattr(settings, "OCR_ENGINE", "gemini").lower() == "gemini" and bool(getattr(settings, "GOOGLE_API_KEY", None))
                logger.info("Starting %s OCR on '%s' (%d pages)", "Gemini Cloud Vision" if use_gemini else "EasyOCR", filename, total_pages)

                for page_num, page in enumerate(pdf):
                    try:
                        pil_img = page_to_pil(page, self.dpi, settings.OCR_MAX_PX)
                        doc = None
                        if use_gemini:
                            doc = self.ocr_page_gemini(page_num, pil_img, filename, pdf_path)
                            if doc is None:
                                raw_text = page.get_text("text") if hasattr(page, "get_text") else ""
                                page_text = raw_text.strip() if isinstance(raw_text, str) else ""
                                if page_text:
                                    doc = Document(
                                        page_content=page_text,
                                        metadata={
                                            "source": pdf_path,
                                            "filename": filename,
                                            "page_number": page_num + 1,
                                            "section": detect_section(page_text),
                                            "parser_used": "pymupdf_fallback",
                                            "is_ocr": False,
                                            "document_type": "pdf_scanned",
                                        },
                                    )
                        else:
                            img_array = np.array(pil_img)
                            doc = self.ocr_page_worker(page_num, img_array, filename, pdf_path, self.languages)
                            del img_array

                        if doc:
                            documents.append(doc)

                        del pil_img
                        gc.collect()

                        logger.info("OCR Progress: %d/%d pages processed ('%s')", page_num + 1, total_pages, filename)
                        if progress_callback:
                            progress_callback(page_num + 1, total_pages, f"🔍 Reading scanned document: {page_num + 1} of {total_pages} pages analysed…")
                    except Exception as page_err:
                        logger.warning("OCR worker failed on page %d of '%s': %s — skipping.", page_num + 1, filename, page_err)

        except Exception as open_error:
            raise RuntimeError(f"Could not open '{pdf_path}': {open_error}") from open_error
        finally:
            unload_reader()

        logger.info("OCR complete: %d/%d pages extracted from '%s'.", len(documents), total_pages, filename)
        gc.collect()
        return documents

    def ocr_page_gemini(
        self,
        page_num: int,
        pil_image: Image.Image,
        filename: str,
        pdf_path: str,
    ) -> Optional[Document]:
        page_label = page_num + 1
        global genai
        if genai is None:
            try:
                # pyrefly: ignore [missing-import]
                import google.generativeai as genai
            except ImportError:
                logger.error("google.generativeai not installed for Gemini Cloud OCR.")
                return None

        try:
            genai.configure(api_key=settings.GOOGLE_API_KEY)
        except Exception as cfg_err:
            logger.warning("Failed to configure genai API key: %s", cfg_err)
            return None

        target_model = getattr(settings, "OCR_MODEL_NAME", None) or "gemini-3.6-flash"
        candidate_models = [target_model]
        for fallback_name in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-3.7-flash"]:
            if fallback_name not in candidate_models:
                candidate_models.append(fallback_name)

        prompt = (
            "Extract all text, numbers, structures, and tables from this document image page cleanly into markdown format. "
            "Do not summarize or invent facts. Preserve exact numbers, dates, IDs, and structure."
        )

        for model_name in candidate_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content([prompt, pil_image])
                page_text = (response.text or "").strip()

                if page_text:
                    return Document(
                        page_content=page_text,
                        metadata={
                            "source": pdf_path,
                            "filename": filename,
                            "page_number": page_label,
                            "section": detect_section(page_text),
                            "parser_used": f"gemini_{model_name}",
                            "is_ocr": True,
                            "document_type": "pdf_scanned",
                            "ocr_confidence": 0.99,
                        },
                    )
            except Exception as model_err:
                logger.warning("Gemini Vision OCR with '%s' failed for page %d (%s)", model_name, page_label, model_err)

        return None

    def ocr_page_worker(
        self,
        page_num: int,
        img_array: np.ndarray,
        filename: str,
        pdf_path: str,
        languages: List[str],
    ) -> Optional[Document]:
        import torch
        page_label = page_num + 1
        reader = get_reader(languages)
        with torch.no_grad():
            raw_results = reader.readtext(
                img_array,
                batch_size=settings.OCR_BATCH_SIZE,
                decoder=settings.OCR_DECODER,
                beamWidth=settings.OCR_BEAM_WIDTH,
                workers=settings.OCR_WORKERS,
                mag_ratio=settings.OCR_MAG_RATIO,
                contrast_ths=settings.OCR_CONTRAST_THS,
                adjust_contrast=settings.OCR_ADJUST_CONTRAST,
                text_threshold=settings.OCR_TEXT_THRESHOLD,
                low_text=settings.OCR_LOW_TEXT,
                link_threshold=settings.OCR_LINK_THRESHOLD,
            )
        if not raw_results:
            logger.debug("Page %d: no text detected.", page_label)
            return None

        valid_items = [(t.strip(), conf) for _, t, conf in sort_into_reading_order(raw_results) if t.strip()]
        if not valid_items:
            return None

        lines, confidences = zip(*valid_items)
        page_text = "\n".join(lines)
        mean_conf = float(np.mean(confidences))

        return Document(
            page_content=page_text,
            metadata={
                "source": pdf_path,
                "filename": filename,
                "page_number": page_label,
                "section": detect_section(page_text),
                "parser_used": "easyocr",
                "is_ocr": True,
                "document_type": "pdf_scanned",
                "ocr_confidence": round(mean_conf, 4),
            },
        )
