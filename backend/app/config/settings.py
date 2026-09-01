from pydantic_settings import BaseSettings
from pydantic import Field
import os

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="sqlite:///./multimedia_assistant.db")
    QDRANT_LOCAL_PATH: str = Field(default="./storage/qdrant")
    QDRANT_COLLECTION_NAME: str = Field(default="multimedia_knowledge_base")
    
    LLM_PROVIDER: str = Field(default="gpt-oss-120b")
    GROQ_API_KEY: str = Field(default="")
    GOOGLE_API_KEY: str = Field(default="")
    COHERE_API_KEY: str = Field(default="")
    
    EMBEDDING_PROVIDER: str = Field(default="google")
    RERANKER_PROVIDER: str = Field(default="cohere")
    RERANKER_MODEL_NAME: str = Field(default="rerank-v4.0-fast")
    
    UPLOAD_DIR: str = Field(default="./storage/uploads")
    TRANSCRIPT_DIR: str = Field(default="./storage/transcripts")
    TEMP_DIR: str = Field(default="./storage/temp")
    
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_RELOAD: bool = Field(default=True)
    
    FRONTEND_PORT: int = Field(default=8501)

    OCR_DPI: int = Field(default=400)
    OCR_LANGUAGE: str = Field(default="en")
    OCR_SCANNED_CHAR_THRESHOLD: int = Field(default=10)
    OCR_MAX_WORKERS: int = Field(default=0)

    ENABLE_DOCLING: bool = Field(default=False)

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.env")
        case_sensitive = False
        extra = "ignore"


settings = Settings()