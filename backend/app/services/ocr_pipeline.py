import gc
import logging
import os
import re
import threading
import warnings
from typing import Callable, List, Optional, Any, Union

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

LANG_MAP = {
    "en": "eng", "es": "spa", "fr": "fra", "de": "deu",
    "it": "ita", "pt": "por", "ru": "rus", "zh": "chi_sim",
    "ja": "jpn", "ar": "ara", "hi": "hin", "nl": "nld",
    "pl": "pol", "tr": "tur", "uk": "ukr", "cs": "ces",
    "sv": "swe", "da": "dan", "fi": "fin", "no": "nor",
}


def normalize_languages(languages: List[str]) -> str:
    normalized = []
    for lang in (languages or ["eng"]):
        l = str(lang).strip().lower()
        normalized.append(LANG_MAP.get(l, l))
    return "+".join(normalized) if normalized else "eng"


def unload_reader():
    gc.collect()


def get_reader(languages: List[str]) -> Any:
    try:
        import pytesseract
        return pytesseract
    except ImportError:
        raise ImportError("pytesseract is not installed. Run: pip install pytesseract")


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
    if not isinstance(text, str):
        return None
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
                use_gemini = getattr(settings, "OCR_ENGINE", "tesseract").lower() == "gemini" and bool(getattr(settings, "GOOGLE_API_KEY", None))
                logger.info("Starting %s OCR on '%s' (%d pages)", "Gemini Cloud Vision" if use_gemini else "Tesseract OCR", filename, total_pages)

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
                            doc = self.ocr_page_worker(page_num, pil_img, filename, pdf_path, self.languages)

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
        img_input: Any,
        filename: str,
        pdf_path: str,
        languages: List[str],
    ) -> Optional[Document]:
        import pytesseract

        page_label = page_num + 1
        lang_str = normalize_languages(languages)

        tess_cmd = getattr(settings, "TESSERACT_CMD", None) or os.environ.get("TESSERACT_CMD")
        if tess_cmd:
            pytesseract.pytesseract.tesseract_cmd = tess_cmd

        psm = getattr(settings, "OCR_PSM", 3)
        oem = getattr(settings, "OCR_OEM", 3)
        tess_config = f"--psm {psm} --oem {oem}"

        if isinstance(img_input, np.ndarray):
            pil_image = Image.fromarray(img_input)
        elif isinstance(img_input, Image.Image):
            pil_image = img_input
        else:
            raise ValueError(f"Unsupported image format for Tesseract worker: {type(img_input)}")

        try:
            raw_output = pytesseract.image_to_string(
                pil_image,
                lang=lang_str,
                config=tess_config,
                output_type=pytesseract.Output.STRING,
            )
            if isinstance(raw_output, dict):
                text_val = raw_output.get("text", "")
                if isinstance(text_val, list):
                    page_text = " ".join(str(x) for x in text_val).strip()
                else:
                    page_text = str(text_val).strip()
            elif isinstance(raw_output, (list, tuple)):
                page_text = " ".join(str(x) for x in raw_output).strip()
            elif raw_output is not None:
                page_text = str(raw_output).strip()
            else:
                page_text = ""
        except Exception as ocr_exc:
            logger.warning("Tesseract image_to_string failed on page %d of '%s': %s", page_label, filename, ocr_exc)
            return None

        if not page_text:
            logger.debug("Page %d of '%s': no text detected by Tesseract.", page_label, filename)
            return None

        mean_conf = 0.95
        try:
            data = pytesseract.image_to_data(pil_image, lang=lang_str, config=tess_config, output_type=pytesseract.Output.DICT)
            confs = [
                float(c) for c, t in zip(data.get("conf", []), data.get("text", []))
                if float(c) >= 0 and str(t).strip()
            ]
            if confs:
                mean_conf = float(np.mean(confs)) / 100.0
        except Exception as conf_err:
            logger.debug("Could not compute Tesseract confidence for page %d of '%s': %s", page_label, filename, conf_err)

        return Document(
            page_content=page_text,
            metadata={
                "source": pdf_path,
                "filename": filename,
                "page_number": page_label,
                "section": detect_section(page_text),
                "parser_used": "tesseract",
                "is_ocr": True,
                "document_type": "pdf_scanned",
                "ocr_confidence": round(mean_conf, 4),
            },
        )

