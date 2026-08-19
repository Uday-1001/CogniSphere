from __future__ import annotations
import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from ..vectorstore.qdrant import qdrant_service
from ..config.settings import settings

logger = logging.getLogger(__name__)


reranker_client = None
reranker_initialized = False

def get_reranker(top_n: int = 4) -> Optional[CohereRerank]:
    if settings.RERANKER_PROVIDER == "cohere" and settings.COHERE_API_KEY:
        try:
            return CohereRerank(
                cohere_api_key=settings.COHERE_API_KEY,
                model=settings.RERANKER_MODEL_NAME or "rerank-english-v3.0",
                top_n=top_n
            )
        except Exception as _reranker_err:
            logger.warning(
                "Cohere reranker unavailable (%s). "
                "Retrieval will use base retrieval without reranking.",
                _reranker_err,
            )
    return None


class RetrievalService:

    def get_retriever(
        self,
        search_k: int = 4,
        filter_by_file_id: Optional[int] = None,
    ):
        from qdrant_client import models
        where_clause = None
        if filter_by_file_id is not None:
            where_clause = models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.document_id",
                        match=models.MatchValue(value=str(filter_by_file_id)),
                    )
                ]
            )

        if qdrant_service.vectorstore is None:
            from .embeddings import embedding_service
            qdrant_service.initialize(embedding_service.get_embeddings())

        vectorstore = qdrant_service.vectorstore
        if vectorstore is None:
            raise RuntimeError("Qdrant vectorstore could not be initialized.")

        reranker = get_reranker(top_n=search_k)
        candidate_k = search_k * 2 if reranker is not None else search_k

        base_retriever = vectorstore.as_retriever(
            search_kwargs={
                "k":      candidate_k,
                **({"filter": where_clause} if where_clause else {}),
            },
        )

        if reranker is not None:
            return ContextualCompressionRetriever(
                base_compressor=reranker,
                base_retriever=base_retriever,
            )

        return base_retriever

    def retrieve_documents(
        self,
        query: str,
        number_of_results: int = 4,
        filter_by_file_id: Optional[int] = None,
    ) -> List[Document]:
        retriever = self.get_retriever(
            search_k=number_of_results,
            filter_by_file_id=filter_by_file_id,
        )
        return retriever.invoke(query)


retrieval_service = RetrievalService()