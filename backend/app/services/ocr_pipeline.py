import logging
import os
import re
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Any

import fitz
import numpy as np
from langchain_core.documents import Document
from PIL import Image, ImageEnhance

for env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[env_var] = "1"

warnings.filterwarnings("ignore", message=".*pin_memory.*")
logger = logging.getLogger(__name__)

_thread_local = threading.local()


def get_reader(languages: List[str]) -> Any:
    if not hasattr(_thread_local, "reader"):
        try:
            import torch
            import easyocr
            torch.set_num_threads(max(1, (os.cpu_count() or 1) // 4))
            logger.info("Thread %s: initialising EasyOCR (langs=%s)...", threading.current_thread().name, languages)
            _thread_local.reader = easyocr.Reader(languages, gpu=False, verbose=False)
        except ImportError:
            raise ImportError("EasyOCR is not installed. Run: pip install easyocr")
    return _thread_local.reader


def page_to_image(page: fitz.Page, dpi: int, max_px: int = 6000) -> np.ndarray:
    pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False, colorspace=fitz.csRGB)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    w, h = image.size
    if max(w, h) > max_px:
        scale = max_px / max(w, h)
        image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    return np.array(ImageEnhance.Contrast(image).enhance(1.5))


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


class PDFOCRPipeline:
    SCANNED_CHAR_THRESHOLD = 10

    def __init__(
        self,
        dpi: int = 150,
        languages: Optional[List[str]] = None,
        char_threshold: Optional[int] = None,
        max_workers: Optional[int] = None,
    ):
        self.dpi = dpi
        self.languages = languages or ["en"]
        self.max_workers = max_workers or max(1, (os.cpu_count() or 1) // 2)
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
        try:
            with fitz.open(pdf_path) as pdf:
                total_pages = len(pdf)
                logger.info("Starting OCR on '%s' (%d pages, %d rasterisation workers)", filename, total_pages, self.max_workers)
                page_arrays = {}
                for i, page in enumerate(pdf): # type: ignore
                    try:
                        page_arrays[i] = page_to_image(page, self.dpi)
                    except Exception as e:
                        logger.warning("Could not rasterise page %d: %s — skipping.", i + 1, e)
        except Exception as open_error:
            raise RuntimeError(f"Could not open '{pdf_path}': {open_error}") from open_error

        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(self.ocr_page_worker, i, arr, filename, pdf_path, self.languages): i
                for i, arr in page_arrays.items()
            }
            completed = 0
            for future in as_completed(futures):
                page_num = futures[future]
                completed += 1
                try:
                    doc = future.result()
                    if doc:
                        results[page_num] = doc
                    logger.info("OCR Progress: %d/%d pages processed ('%s')", completed, total_pages, filename)
                    if progress_callback:
                        progress_callback(completed, total_pages, f"🔍 Reading scanned document: {completed} of {total_pages} pages analysed…")
                except Exception as worker_error:
                    logger.warning("OCR worker failed on page %d: %s — skipping.", page_num + 1, worker_error)

        documents = [results[i] for i in sorted(results)]
        logger.info("OCR complete: %d/%d pages extracted from '%s'.", len(documents), total_pages, filename)
        return documents

    def ocr_page_worker(
        self,
        page_num: int,
        img_array: np.ndarray,
        filename: str,
        pdf_path: str,
        languages: List[str],
    ) -> Optional[Document]:
        page_label = page_num + 1
        reader = get_reader(languages)
        raw_results = reader.readtext(
            img_array, batch_size=4, decoder='beamsearch', mag_ratio=1.5, adjust_contrast=0.5
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
