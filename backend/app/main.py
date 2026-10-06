import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api import upload, chat, history, health
from .database.connection import init_db, SessionLocal
from .database.models import UploadedFile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

init_db()

async def _sync_qdrant_with_db() -> None:
    logger = logging.getLogger(__name__)
    try:
        from .vectorstore.qdrant import qdrant_service
        from .config.settings import settings

        client = qdrant_service.get_client()
        collection = settings.QDRANT_COLLECTION_NAME

        collections = [c.name for c in client.get_collections().collections]
        if collection not in collections:
            logger.info("Startup sync: Qdrant collection '%s' does not exist yet — nothing to purge.", collection)
            return

        all_qdrant_doc_ids: set = set()
        offset = None
        while True:
            result, next_offset = client.scroll(
                collection_name=collection,
                limit=500,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in result:
                payload = point.payload or {}
                doc_id = (payload.get("metadata") or {}).get("document_id")
                if doc_id is not None:
                    all_qdrant_doc_ids.add(str(doc_id))
            if next_offset is None:
                break
            offset = next_offset

        if not all_qdrant_doc_ids:
            logger.info("Startup sync: Qdrant collection is empty — nothing to purge.")
            return

        db = SessionLocal()
        try:
            valid_ids: set = {
                str(row.id)
                for row in db.query(UploadedFile.id).filter(
                    UploadedFile.status == "processed"
                ).all()
            }
        finally:
            db.close()

        stale_ids = all_qdrant_doc_ids - valid_ids

        if not stale_ids:
            logger.info(
                "Startup sync: All %d Qdrant document IDs are valid — no purge needed.",
                len(all_qdrant_doc_ids),
            )
            return

        logger.warning(
            "Startup sync: Found %d stale document IDs in Qdrant with no matching DB record: %s — purging now.",
            len(stale_ids),
            stale_ids,
        )

        from qdrant_client.models import Filter, FieldCondition, MatchAny
        stale_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.document_id",
                    match=MatchAny(any=list(stale_ids)),
                )
            ]
        )
        client.delete(
            collection_name=collection,
            points_selector=stale_filter,  # type: ignore[arg-type]
        )
        logger.info(
            "Startup sync: Successfully purged stale chunks for document IDs: %s",
            stale_ids,
        )

    except Exception as sync_err:
        logging.getLogger(__name__).error(
            "Startup sync: Qdrant-DB sync failed (non-fatal): %s", sync_err
        )



@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Hello! Starting up the AI Multimedia Knowledge Assistant API...")
    await _sync_qdrant_with_db()
    yield
    logging.info("Shutting down the API. See you next time!")


app = FastAPI(
    title="AI Multimedia Knowledge Assistant",
    description="Your friendly RAG assistant for multimedia content. Upload files and chat with them!",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(history.router)

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


