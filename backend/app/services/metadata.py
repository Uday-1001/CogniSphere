import uuid
from typing import Optional, List, Dict
from langchain_core.documents import Document

class MetadataEnricher:

    def enrich(
        self,
        document: Document,
        file_id: int,
        filename: str,
        chunk_number: int,
        page_number: Optional[int] = None,
        timestamp_start: Optional[str] = None,
        timestamp_end: Optional[str] = None,
        section: Optional[str] = None,
        parser_used: Optional[str] = None,
        is_ocr: Optional[bool] = None,
        document_type: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        language: str = "en",
    ) -> Document:
        meta = document.metadata

        meta["document_id"]   = str(file_id)
        meta["filename"]      = filename
        meta["chunk_number"]  = chunk_number
        meta["embedding_id"]  = str(uuid.uuid4())
        meta["language"]      = language

        meta["page_number"] = (
            page_number
            if page_number is not None
            else meta.get("page_number") or meta.get("page")
        )
        meta["timestamp_start"] = timestamp_start
        meta["timestamp_end"]   = timestamp_end

        meta["section"] = (
            section
            if section is not None
            else meta.get("section")
        )
        meta["parser_used"] = (
            parser_used
            if parser_used is not None
            else meta.get("parser_used", "unknown")
        )
        meta["is_ocr"] = (
            is_ocr
            if is_ocr is not None
            else meta.get("is_ocr", False)
        )
        meta["document_type"] = (
            document_type
            if document_type is not None
            else meta.get("document_type", "digital")
        )

        meta["ocr_confidence"] = (
            ocr_confidence
            if ocr_confidence is not None
            else meta.get("ocr_confidence")
        )

        meta.pop("page", None)

        return document


    def extract_timestamps_from_segments(
        self,
        content: str,
        segments: List[Dict],
    ) -> tuple:
        if not segments:
            return None, None

        words = content.split()
        if not words:
            return None, None

        content_start = " ".join(words[:5])
        content_end = " ".join(words[-5:])

        ts_start = segments[0].get("start")
        ts_end = segments[-1].get("end")

        for segment in segments:
            seg_text = segment.get("text", "")
            if content_start in seg_text or seg_text.startswith(content[:20]):
                ts_start = segment.get("start")
                break

        for segment in reversed(segments):
            seg_text = segment.get("text", "")
            if content_end in seg_text or seg_text.endswith(content[-20:]):
                ts_end = segment.get("end")
                break

        return ts_start, ts_end