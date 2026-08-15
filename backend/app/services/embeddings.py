from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from ..config.settings import settings
from typing import Optional


class EmbeddingService:
    _instance = None
    _embeddings: Optional[Embeddings] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # Generating the embeddings 
    def get_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            if settings.EMBEDDING_PROVIDER == "huggingface":
                self._embeddings = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5"
                )
            else:
                raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}")
        
        return self._embeddings


embedding_service = EmbeddingService()