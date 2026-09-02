import gc
from typing import List, Optional
import logging
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList, VectorParams, Distance, SparseVectorParams
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from langchain_core.embeddings import Embeddings
from ..config.settings import settings

logger = logging.getLogger(__name__)

class QdrantService:
    _instance = None
    _client: Optional[QdrantClient] = None
    _vectorstore: Optional[QdrantVectorStore] = None
    _init_failed: bool = False 

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self) -> QdrantClient:
        if self._client is None:
            if self._init_failed:
                raise RuntimeError("Qdrant initialization previously failed. Restart the server to retry.")
            try:
                if settings.QDRANT_URL:
                    self._client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
                    logger.info("Connected to remote Qdrant instance at '%s'", settings.QDRANT_URL)
                else:
                    qdrant_path = getattr(settings, "QDRANT_LOCAL_PATH", None) or "./storage/qdrant"
                    os.makedirs(qdrant_path, exist_ok=True)
                    self._client = QdrantClient(path=qdrant_path)
                    logger.info("Using embedded local Qdrant storage at '%s'", qdrant_path)
            except Exception as e:
                self._init_failed = True
                logger.error("Failed to initialize QdrantClient: %s", e)
                raise
        return self._client

    def initialize(self, embedding_function: Embeddings):
        if self._init_failed:
            raise RuntimeError(
                "Qdrant initialization previously failed. Restart the server to retry."
            )

        client = self.get_client()

        if self._vectorstore is None:
            from langchain_qdrant import FastEmbedSparse
            sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
            try:
                self._vectorstore = QdrantVectorStore(
                    client=client,
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    embedding=embedding_function,
                    sparse_embedding=sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID,
                )
            except Exception as e:
                logger.warning(
                    "Collection '%s' not found or incompatible (%s). Recreating...",
                    settings.QDRANT_COLLECTION_NAME, e,
                )
                try:
                    client.delete_collection(settings.QDRANT_COLLECTION_NAME)
                except Exception:
                    pass

                try:
                    dummy_vector = embedding_function.embed_query("test")
                    client.create_collection(
                        collection_name=settings.QDRANT_COLLECTION_NAME,
                        vectors_config=VectorParams(
                            size=len(dummy_vector), distance=Distance.COSINE
                        ),
                        sparse_vectors_config={"langchain-sparse": SparseVectorParams()},
                    )
                except Exception as create_err:
                    self._init_failed = True
                    logger.error("Failed to recreate collection: %s", create_err)
                    raise

                self._vectorstore = QdrantVectorStore(
                    client=client,
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    embedding=embedding_function,
                    sparse_embedding=sparse_embeddings,
                    retrieval_mode=RetrievalMode.HYBRID,
                )
        return self._vectorstore

    @property
    def vectorstore(self) -> Optional[QdrantVectorStore]:
        if self._init_failed:
            return None
        if self._vectorstore is None:
            from ..services.embeddings import embedding_service
            self.initialize(embedding_service.get_embeddings())
        return self._vectorstore

    def reset(self):
        if self._client:
            try:
                self._client.delete_collection(settings.QDRANT_COLLECTION_NAME)
            except Exception:
                pass
            self._vectorstore = None
            gc.collect()

    def add_documents(self, texts: List[str], metadatas: List[dict], ids: List[str]):
        if self.vectorstore is None:
            raise ValueError("Vectorstore not initialized and failed to auto-initialize.")
        self.vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        gc.collect()

    def similarity_search(self, query: str, k: int = 4):
        if self.vectorstore is None:
            raise ValueError("Vectorstore not initialized and failed to auto-initialize.")
        return self.vectorstore.similarity_search(query=query, k=k)

    def similarity_search_with_score(self, query: str, k: int = 4):
        if self.vectorstore is None:
            raise ValueError("Vectorstore not initialized and failed to auto-initialize.")
        return self.vectorstore.similarity_search_with_score(query=query, k=k)

    def delete(self, ids: Optional[List[str]] = None, where: Optional[dict] = None):
        client = self.get_client()
        try:
            if ids:
                client.delete(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    points_selector=PointIdsList(points=ids), # type: ignore
                )
            elif where:
                conditions = [
                    FieldCondition(key=f"metadata.{key}", match=MatchValue(value=value))
                    for key, value in where.items()
                ]
                client.delete(
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    points_selector=Filter(must=conditions), # type: ignore
                )
        except Exception as exc:
            logger.warning("Qdrant delete skipped or failed (collection may not exist yet): %s", exc)
        finally:
            gc.collect()

qdrant_service = QdrantService()

