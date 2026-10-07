import os
import gc
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from ..database.connection import get_db
from ..database.models import ChatSession, UploadedFile
from datetime import datetime
from sqlalchemy import text
from .deps import get_tenant_id
from ..config.settings import settings

router = APIRouter(prefix="/history", tags=["history"])


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: Optional[str] = None
    timestamp_references: Optional[str] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    session_id: int
    title: Optional[str]
    messages: List[ChatMessageResponse]


class BulkDeleteRequest(BaseModel):
    file_ids: List[int]

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime


@router.get("/sessions", response_model=List[ChatHistoryResponse])
async def get_chat_sessions(
    db=Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id),
):
    from sqlalchemy.orm import selectinload

    sessions_query = db.query(ChatSession).options(
        selectinload(ChatSession.messages)
    )
                                                               
    if tenant_id is not None:
        sessions_query = sessions_query.filter(ChatSession.tenant_id == tenant_id)

    chat_sessions = sessions_query.order_by(
        ChatSession.created_at.desc()
    ).limit(20).all()

    result = []
    for session in chat_sessions:
        messages = sorted(session.messages, key=lambda m: m.created_at)

        result.append(ChatHistoryResponse(
            session_id=session.id,
            title=session.title,
            messages=[ChatMessageResponse(
                id=message.id,
                role=message.role,
                content=message.content,
                sources=message.sources,
                timestamp_references=message.timestamp_references,
                created_at=message.created_at
            ) for message in messages]
        ))

    gc.collect()
    return result


@router.get("/documents", response_model=List[DocumentResponse])
async def get_documents(
    db=Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id),
):
    docs_query = db.query(UploadedFile)
    if tenant_id is not None:
        docs_query = docs_query.filter(UploadedFile.tenant_id == tenant_id)

    documents = docs_query.order_by(UploadedFile.created_at.desc()).limit(50).all()

    res = [DocumentResponse(
        id=document.id,
        filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        created_at=document.created_at
    ) for document in documents]

    gc.collect()
    return res


@router.delete("/document/{file_id}")
async def delete_document(
    file_id: int,
    db=Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id),
):
    file_query = db.query(UploadedFile).filter(UploadedFile.id == file_id)
    if tenant_id is not None:
        file_query = file_query.filter(UploadedFile.tenant_id == tenant_id)
    database_file_record = file_query.first()
    if not database_file_record:
        raise HTTPException(
            status_code=404,
            detail="We couldn't locate that document in the database.")

    if database_file_record.file_path and os.path.exists(
            database_file_record.file_path):
        try:
            os.remove(database_file_record.file_path)
        except Exception:
            pass

    if database_file_record.transcript_path and os.path.exists(
            database_file_record.transcript_path):
        try:
            os.remove(database_file_record.transcript_path)
        except Exception:
            pass

    from ..vectorstore.qdrant import qdrant_service
    try:
        qdrant_where: dict = {"document_id": str(file_id)}
        if tenant_id is not None:
            qdrant_where["tenant_id"] = str(tenant_id)
        qdrant_service.delete(where=qdrant_where)
    except Exception:
        pass

    db.delete(database_file_record)
    if settings.DATABASE_URL.startswith("sqlite"):
        try:
            db.execute(text("UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM uploaded_files) WHERE name = 'uploaded_files'"))
        except Exception:
            pass
    db.commit()

    gc.collect()
    return {"message": "Document deleted successfully"}


@router.delete("/documents/bulk")
async def bulk_delete_documents(
    request: BulkDeleteRequest,
    db=Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id),
):
    deleted_ids = []
    from ..vectorstore.qdrant import qdrant_service

    for file_id in request.file_ids:
        file_query = db.query(UploadedFile).filter(UploadedFile.id == file_id)
        if tenant_id is not None:
            file_query = file_query.filter(UploadedFile.tenant_id == tenant_id)
        database_file_record = file_query.first()
        if not database_file_record:
            continue
            
        if database_file_record.file_path and os.path.exists(database_file_record.file_path):
            try:
                os.remove(database_file_record.file_path)
            except Exception:
                pass

        if database_file_record.transcript_path and os.path.exists(database_file_record.transcript_path):
            try:
                os.remove(database_file_record.transcript_path)
            except Exception:
                pass

        try:
            qdrant_where: dict = {"document_id": str(file_id)}
            if tenant_id is not None:
                qdrant_where["tenant_id"] = str(tenant_id)
            qdrant_service.delete(where=qdrant_where)
        except Exception:
            pass

        db.delete(database_file_record)
        deleted_ids.append(file_id)

    if deleted_ids:
        if settings.DATABASE_URL.startswith("sqlite"):
            try:
                db.execute(text("UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM uploaded_files) WHERE name = 'uploaded_files'"))
            except Exception:
                pass
        db.commit()

    gc.collect()
    return {"message": f"Successfully deleted {len(deleted_ids)} documents.", "deleted_ids": deleted_ids}

