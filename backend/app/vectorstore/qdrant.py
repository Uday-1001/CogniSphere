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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_client(self) -> QdrantClient:
        if self._client is None:
            try:
                raw_url = getattr(settings, "QDRANT_URL", None)
                raw_api_key = getattr(settings, "QDRANT_API_KEY", None)
                url = raw_url.strip().rstrip("/") if raw_url and raw_url.strip() else None
                api_key = raw_api_key.strip() if raw_api_key and raw_api_key.strip() else None

                if url:
                    self._client = QdrantClient(url=url, api_key=api_key)
                    logger.info("Connected to remote Qdrant instance at '%s'", url)
                else:
                    qdrant_path = getattr(settings, "QDRANT_LOCAL_PATH", None) or "./storage/qdrant"
                    os.makedirs(qdrant_path, exist_ok=True)
                    self._client = QdrantClient(path=qdrant_path)
                    logger.info("Using embedded local Qdrant storage at '%s'", qdrant_path)
            except Exception as e:
                logger.error("Failed to initialize QdrantClient: %s", e)
                raise
        return self._client

    def _create_payload_indexes(self, client: QdrantClient):
        try:
            from qdrant_client.models import PayloadSchemaType
            client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                field_name="metadata.document_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.info("Ensured KEYWORD payload index for 'metadata.document_id'")
        except Exception as idx_err:
            logger.debug("Payload index creation notice: %s", idx_err)

    def initialize(self, embedding_function: Embeddings):
        client = self.get_client()

        if self._vectorstore is None:
            sparse_embeddings = None
            retrieval_mode = RetrievalMode.DENSE
            try:
                from langchain_qdrant import FastEmbedSparse
                sparse_embeddings = FastEmbedSparse(model_name="Qdrant/bm25")
                retrieval_mode = RetrievalMode.HYBRID
            except Exception as fastembed_err:
                logger.warning("FastEmbedSparse (BM25) initialization skipped/failed (%s) — using DENSE mode.", fastembed_err)

            try:
                self._vectorstore = QdrantVectorStore(
                    client=client,
                    collection_name=settings.QDRANT_COLLECTION_NAME,
                    embedding=embedding_function,
                    sparse_embedding=sparse_embeddings,
                    retrieval_mode=retrieval_mode,
                )
                self._create_payload_indexes(client)
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
                    self._create_payload_indexes(client)
                except Exception as create_err:
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

