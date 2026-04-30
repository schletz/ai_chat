"""FastAPI entry point for the Gemma 4 Chat API."""

import asyncio
import datetime
import gc
import logging
import os
import sys
import time
import _thread
import threading
import uvicorn

from typing import Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import auth, characters, chat, system
from config_manager import ConfigManager
from llm_service import LLMService
from tool_collection import LLMToolCollection


load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("🚨 ERROR: SECRET_KEY was not found in the .env file!")

MODEL_PATH = os.getenv("MODEL_PATH")
if not MODEL_PATH:
    raise ValueError("🚨 ERROR: MODEL_PATH was not found in the .env file!")

DATA_DIR = os.getenv("DATA_DIR", "data")
TOOLS_DIR = os.getenv("TOOLS_DIR", "tools")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SSL_KEYFILE = os.getenv("SSL_KEYFILE", "key.pem")
SSL_CERTFILE = os.getenv("SSL_CERTFILE", "cert.pem")

CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

ALGORITHM = "HS256"


logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="(%(asctime)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


llm_service = None

# Serializes concurrent inference requests to prevent VRAM contention.
llm_lock = asyncio.Lock()

config_manager = ConfigManager(DATA_DIR)
llm_tool_collection = LLMToolCollection(TOOLS_DIR, DATA_DIR, config_manager, llm_service)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    global llm_service

    app.state.config_manager = config_manager
    app.state.llm_lock = llm_lock
    app.state.data_dir = DATA_DIR
    app.state.secret_key = SECRET_KEY
    app.state.algorithm = ALGORITHM

    active_model = config_manager.get_active_model_data()
    if not active_model:
        logger.critical("🚨 CRITICAL ERROR: No active model found in config!")
        yield
        return

    model_path = active_model["file_path"]
    n_ctx = active_model.get("n_ctx", 32768)

    logger.info(f"🚀 Loading model '{active_model['id']}' from {model_path} into VRAM...")

    try:
        llm_service = LLMService.from_modelfile(model_path, n_ctx=n_ctx)
        app.state.llm_service = llm_service
        app.state.llm_tool_collection = LLMToolCollection(TOOLS_DIR, DATA_DIR, config_manager, llm_service)
        logger.info("✅ Model successfully loaded and ready.")
        yield
    except Exception as e:
        logger.error(f"🚨 Error loading model: {e}")
        yield
    finally:
        logger.info("🛑 Shutting down server and clearing VRAM...")
        if llm_service:
            del llm_service
        gc.collect()


app = FastAPI(
    title="Gemma 4 Chat API",
    description="REST API for local LLM interaction with character routing and JWT auth.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(system.router)


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=HOST,
        port=PORT,
        ssl_keyfile=SSL_KEYFILE,
        ssl_certfile=SSL_CERTFILE,
        timeout_graceful_shutdown=5,
    )