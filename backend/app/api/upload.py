from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, TypedDict
import os
import uuid
import shutil
import logging
from langgraph.graph import StateGraph, END
from ..database.connection import get_db, SessionLocal
from ..database.models import UploadedFile
from sqlalchemy import text
from ..services.transcription import transcription_service
from ..services.ingestion import ingestion_service
from ..services.embeddings import embedding_service
from ..vectorstore.qdrant import qdrant_service
from ..config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

processing_progress: Dict[int, dict] = {}


class UploadResponse(BaseModel):
    file_id: int
    filename: str
    file_type: str
    status: str
    message: str


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: str


class ProgressResponse(BaseModel):
    file_id: int
    status: str
    current: int
    total: int
    message: str


class IngestionState(TypedDict, total=False):
    file_id: int
    file_path: str
    filename: str
    file_type: str
    transcript_path: Optional[str]
    segment_timestamps: Optional[List[Dict]]
    documents: List[Any]
    error: Optional[str]


def update_progress(file_id: int, current: int, total: int, message: str = "") -> None:
    processing_progress[file_id] = {
        "current": current,
        "total": total,
        "status": "processing",
        "message": message,
    }


def transcribe_node(state: IngestionState) -> Dict[str, Any]:
    file_type = state["file_type"]
    file_id = state["file_id"]

    try:
        if file_type == "video":
            update_progress(file_id, 0, 100, "🎬 Listening to video and creating transcript...")
            _, transcript_path, segments = transcription_service.transcribe_video(
                state["file_path"], settings.TRANSCRIPT_DIR
            )
            return {"transcript_path": transcript_path, "segment_timestamps": segments}

        elif file_type == "audio":
            update_progress(file_id, 0, 100, "🎧 Listening to audio and creating transcript...")
            _, transcript_path, segments = transcription_service.transcribe_audio_file(
                state["file_path"], settings.TRANSCRIPT_DIR
            )
            return {"transcript_path": transcript_path, "segment_timestamps": segments}

        else:
            update_progress(file_id, 0, 100, "📄 Extracting text from document...")
            return {}

    except Exception as exc:
        logger.error("Transcription failed for file %s: %s", file_id, exc)
        return {"error": str(exc)}


def load_documents(state: IngestionState) -> Dict[str, Any]:
    file_id = state["file_id"]

    def progress_callback(current: int, total: int, msg: str = "") -> None:
        update_progress(file_id, current, total, msg)

    try:
        documents = ingestion_service.process_document(
            file_path=state["file_path"],
            file_id=file_id,
            filename=state["filename"],
            file_type=state["file_type"],
            transcript_path=state.get("transcript_path"),
            segment_timestamps=state.get("segment_timestamps"),
            progress_callback=progress_callback,
        )

        if not documents:
            return {
                "error": (
                    "No text could be extracted from this file, even after attempting OCR. "
                    "The file may be heavily corrupted, password-protected, or contain only "
                    "images with no recognisable characters."
                )
            }

        return {"documents": documents}

    except Exception as exc:
        logger.error("Document loading failed for file %s: %s", file_id, exc)
        return {"error": str(exc)}


def index_node(state: IngestionState) -> Dict[str, Any]:
    file_id = state["file_id"]
    documents = state.get("documents") or []

    try:
        update_progress(file_id, 99, 100, "🧠 Organizing knowledge base...")

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = [str(uuid.uuid4()) for _ in documents]

        if qdrant_service.vectorstore is None:
            
            qdrant_service.initialize(embedding_service.get_embeddings())
            
        qdrant_service.add_documents(texts, metadatas, ids)
        update_progress(file_id, 100, 100, "Done")
        return {}

    except Exception as exc:
        logger.error("Indexing failed for file %s: %s", file_id, exc)
        return {"error": str(exc)}


def route_on_error(state: IngestionState) -> str:
    return "error" if state.get("error") else "continue"


def build_ingestion_graph():
    workflow: StateGraph = StateGraph(IngestionState)

    workflow.add_node("transcribe", transcribe_node)
    workflow.add_node("load_documents", load_documents)
    workflow.add_node("index", index_node)

    workflow.set_entry_point("transcribe")

    workflow.add_conditional_edges(
        "transcribe",
        route_on_error,
        {"error": END, "continue": "load_documents"},
    )
    workflow.add_conditional_edges(
        "load_documents",
        route_on_error,
        {"error": END, "continue": "index"},
    )
    workflow.add_conditional_edges(
        "index",
        route_on_error,
        {"error": END, "continue": END},
    )

    return workflow.compile()


ingestion_graph = build_ingestion_graph()


def run_file_processing(file_id: int) -> None:
    db = SessionLocal()
    try:
        record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not record:
            return

        initial_state: IngestionState = {
            "file_id": file_id,
            "file_path": str(record.file_path),
            "filename": str(record.original_filename),
            "file_type": str(record.file_type),
        }

        final_state: Dict[str, Any] = ingestion_graph.invoke(initial_state)

        if final_state.get("error"):
            raise Exception(final_state["error"])

        if final_state.get("transcript_path"):
            record.transcript_path = final_state["transcript_path"]
        # pyrefly: ignore [bad-assignment]
        record.status = "processed"
        # pyrefly: ignore [bad-assignment]
        record.processing_error = None
        db.commit()

    except Exception as processing_error:
        db.rollback()
        record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if record:
            # We keep the record but mark it as an error
            record.status = "error" # type: ignore
            record.processing_error = str(processing_error) # type: ignore
            db.commit()
            
            if record.file_path and os.path.exists(str(record.file_path)):
                try:
                    os.remove(str(record.file_path))
                except Exception:
                    pass

        processing_progress[file_id] = {
            "current": 0, "total": 0,
            "status": "error", "message": str(processing_error),
        }
    finally:
        db.close()


@router.post("/", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    filename = file.filename or "unknown"
    file_type = ingestion_service.get_file_type(filename)
    if not file_type:
        raise HTTPException(
            status_code=400,
            detail="We don't support this file format just yet. Please try a different one.",
        )

    file_id = uuid.uuid4().hex[:8]
    file_extension = os.path.splitext(filename)[1]
    saved_filename = f"{file_id}{file_extension}"
    save_path = os.path.join(settings.UPLOAD_DIR, saved_filename)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(save_path)

    database_file_record = UploadedFile(
        filename=saved_filename,
        original_filename=filename,
        file_type=file_type,
        file_size=file_size,
        file_path=save_path,
        status="uploaded",
    )
    db.add(database_file_record)
    db.commit()
    db.refresh(database_file_record)

    return UploadResponse(
        file_id=int(str(database_file_record.id)),
        filename=str(database_file_record.original_filename),
        file_type=file_type,
        status="uploaded",
        message="File uploaded successfully. Ready for processing.",
    )


@router.post("/{file_id}/process", response_model=UploadResponse)
async def process_file(
    file_id: int,
    background_tasks: BackgroundTasks,
    db=Depends(get_db),
):
    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(
            status_code=404,
            detail="We couldn't locate that file. Please try uploading it again.",
        )

    if database_file_record.status == "processing":
        return UploadResponse(
            file_id=database_file_record.id,
            filename=database_file_record.original_filename,
            file_type=database_file_record.file_type,
            status="processing",
            message="File is already processing.",
        )

    database_file_record.status = "processing"
    db.commit()

    processing_progress[file_id] = {
        "current": 0, "total": 0,
        "status": "processing", "message": "Starting...",
    }

    # type: ignore
    background_tasks.add_task(run_file_processing, file_id)

    return UploadResponse(
        file_id=database_file_record.id,
        filename=database_file_record.original_filename,
        file_type=database_file_record.file_type,
        status="processing",
        message="File processing started in the background.",
    )


@router.get("/{file_id}/status", response_model=ProgressResponse)
async def get_process_status(file_id: int, db=Depends(get_db)):
    progress = processing_progress.get(file_id)
    if progress and progress.get("status") == "error":
        return ProgressResponse(
            file_id=file_id, status="error",
            current=0, total=0,
            message=progress["message"],
        )

    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(
            status_code=404,
            detail="We couldn't locate that file. Please try uploading it again.",
        )

    if database_file_record.status == "error":
        return ProgressResponse(
            file_id=file_id, status="error",
            current=0, total=0,
            message=database_file_record.processing_error or "Unknown error",
        )

    progress = processing_progress.get(
        file_id,
        {"current": 0, "total": 0, "status": database_file_record.status, "message": ""},
    )

    if database_file_record.status == "processed":
        return ProgressResponse(
            file_id=file_id, status="processed",
            current=progress["total"], total=progress["total"],
            message="Done",
        )

    return ProgressResponse(
        file_id=file_id,
        status=database_file_record.status,
        current=progress["current"],
        total=progress["total"],
        message=progress["message"],
    )


@router.get("/{file_id}/view")
async def view_uploaded_file(file_id: int, db=Depends(get_db)):
    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(status_code=404, detail="We couldn't locate that file.")
    if not os.path.exists(database_file_record.file_path):
        raise HTTPException(status_code=404, detail="The file no longer exists on disk.")
    return FileResponse(
        path=database_file_record.file_path,
        filename=database_file_record.original_filename,
        media_type="application/octet-stream",
    )