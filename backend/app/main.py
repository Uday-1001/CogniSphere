import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api import upload, chat, history, health
from .database.connection import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Hello! Starting up the AI Multimedia Knowledge Assistant API...")
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
