from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import Optional
import os

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="sqlite:///./multimedia_assistant.db")
    QDRANT_LOCAL_PATH: str = Field(default="./storage/qdrant")
    QDRANT_COLLECTION_NAME: str = Field(default="multimedia_knowledge_base")
    QDRANT_URL: Optional[str] = Field(default=None)
    QDRANT_API_KEY: Optional[str] = Field(default=None)
    
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

    OCR_ENGINE: str = Field(default="gemini")
    OCR_MODEL_NAME: str = Field(default="gemini-3.6-flash")

    OCR_DPI: int = Field(default=200)
    OCR_LANGUAGE: str = Field(default="en")
    OCR_SCANNED_CHAR_THRESHOLD: int = Field(default=10)
    OCR_MAX_WORKERS: int = Field(default=1)

    OCR_MAX_PX: int = Field(default=1600)
    OCR_CONTRAST_FACTOR: float = Field(default=1.5)

    OCR_DECODER: str = Field(default="greedy")
    OCR_BEAM_WIDTH: int = Field(default=3)
    OCR_BATCH_SIZE: int = Field(default=1)
    OCR_WORKERS: int = Field(default=0)

    OCR_MAG_RATIO: float = Field(default=1.2)
    OCR_CONTRAST_THS: float = Field(default=0.1)
    OCR_ADJUST_CONTRAST: float = Field(default=0.5)

    OCR_TEXT_THRESHOLD: float = Field(default=0.6)
    OCR_LOW_TEXT: float = Field(default=0.3)
    OCR_LINK_THRESHOLD: float = Field(default=0.4)

    ENABLE_DOCLING: bool = Field(default=False)

    @field_validator(
        "QDRANT_URL", "QDRANT_API_KEY", "GROQ_API_KEY",
        "GOOGLE_API_KEY", "COHERE_API_KEY", "DATABASE_URL",
        mode="before"
    )
    def strip_credentials(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.env")
        case_sensitive = False
        extra = "ignore"


settings = Settings()