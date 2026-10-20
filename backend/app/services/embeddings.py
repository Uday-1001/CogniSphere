from typing import List, Optional
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableLambda
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from ..config.settings import settings


class FallbackEmbeddings(Embeddings):
    def __init__(self, primary: Embeddings, fallback: Embeddings):
        self._embed_docs = RunnableLambda(primary.embed_documents).with_fallbacks(
            [RunnableLambda(fallback.embed_documents)]
        )
        self._embed_query = RunnableLambda(primary.embed_query).with_fallbacks(
            [RunnableLambda(fallback.embed_query)]
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._embed_docs.invoke(texts)

    def embed_query(self, text: str) -> List[float]:
        return self._embed_query.invoke(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await self._embed_docs.ainvoke(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await self._embed_query.ainvoke(text)


class EmbeddingService:
    _instance = None
    _embeddings: Optional[Embeddings] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_embeddings(self) -> Embeddings:
        if self._embeddings is None:
            if settings.EMBEDDING_PROVIDER == "google":
                primary = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-2",
                    google_api_key=settings.GOOGLE_API_KEY,
                )
                fallback = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-001",
                    google_api_key=settings.GOOGLE_API_KEY,
                )
                self._embeddings = FallbackEmbeddings(primary=primary, fallback=fallback)
            else:
                raise ValueError(f"Unknown embedding provider: {settings.EMBEDDING_PROVIDER}")

        return self._embeddings


embedding_service = EmbeddingService()