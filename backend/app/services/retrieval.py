from __future__ import annotations
import logging
from typing import List, Optional
from langchain_core.documents import Document
from langchain_classic.retrievers import ContextualCompressionRetriever
from langchain_community.cross_encoders import HuggingFaceCrossEncoder
from langchain_classic.retrievers.document_compressors import CrossEncoderReranker
from ..vectorstore.qdrant import qdrant_service
from ..config.settings import settings

logger = logging.getLogger(__name__)


cross_encoder_model = None
reranker_initialized = False


def _get_cross_encoder() -> Optional[HuggingFaceCrossEncoder]:
    global cross_encoder_model, reranker_initialized
    if not reranker_initialized:
        reranker_initialized = True
        try:
            _reranker_name = settings.RERANKER_MODEL_NAME or "BAAI/bge-reranker-base"
            cross_encoder_model = HuggingFaceCrossEncoder(
                model_name=_reranker_name
            )
            logger.info("Cross-Encoder reranker loaded: %s", _reranker_name)
        except Exception as _reranker_err:
            cross_encoder_model = None
            logger.warning(
                "CrossEncoder reranker unavailable (%s). "
                "Retrieval will use base retrieval without reranking.",
                _reranker_err,
            )
    return cross_encoder_model


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

        cross_encoder = _get_cross_encoder()
        candidate_k = search_k * 2 if cross_encoder is not None else search_k

        base_retriever = vectorstore.as_retriever(
            search_kwargs={
                "k":      candidate_k,
                **({"filter": where_clause} if where_clause else {}),
            },
        )

        if cross_encoder is not None:
            reranker = CrossEncoderReranker(
                model=cross_encoder,
                top_n=search_k,
            )
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