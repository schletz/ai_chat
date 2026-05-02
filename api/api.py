"""
Gemma 4 Chat API - FastAPI Application Entry Point
==================================================
This file contains all the logic of the REST API, including:
- Configuration & Environment Handling
- Pydantic Schemas for Request/Response Validation
- JWT-based Authentication (Stateless)
- VRAM Management for the Local LLM
- CRUD Endpoints for Characters and Chats
- System/Model Management

Developer Notes:
- The LLM is loaded into VRAM only once at startup. Reloading occurs only 
  upon explicit model change or server restart.
- Authentication uses HttpOnly cookies with JWT. No session storage on the server.
- The shutdown mechanism during model switching uses `_thread.interrupt_main()` to ensure 
  that the 200 OK response reaches the frontend before the process is terminated.
"""

# ==============================================================================
# 1. IMPORTS
# ==============================================================================
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

# Local Modules
from config_manager import ConfigManager
from llm_service import LLMService
from tool_collection import LLMToolCollection


# ==============================================================================
# 2. CONFIGURATION & ENVIRONMENT VARIABLES
# ==============================================================================
load_dotenv()

# Security-critical variables (must be present)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("🚨 ERROR: SECRET_KEY was not found in the .env file!")

MODEL_PATH = os.getenv("MODEL_PATH")
if not MODEL_PATH:
    raise ValueError("🚨 ERROR: MODEL_PATH was not found in the .env file!")

# Optional configuration with defaults
DATA_DIR = os.getenv("DATA_DIR", "data")
TOOLS_DIR = os.getenv("TOOLS_DIR", "tools")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
SSL_KEYFILE = os.getenv("SSL_KEYFILE", "key.pem")
SSL_CERTFILE = os.getenv("SSL_CERTFILE", "cert.pem")

# Parse CORS configuration (supports comma-separated lists)
CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STR.split(",") if origin.strip()]

ALGORITHM = "HS256"


# ==============================================================================
# 3. LOGGING SETUP
# ==============================================================================
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="(%(asctime)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==============================================================================
# 4. GLOBAL STATE & DEPENDENCIES
# ==============================================================================
# Note: llm_service serves as a singleton placeholder for the VRAM state.
# It is initialized in the lifespan context and released on shutdown.
llm_service = None

# asyncio.Lock prevents race conditions during sequential LLM inference.
# Requests are queued until the model is ready or a generation is complete.
llm_lock = asyncio.Lock()

# Central configuration instance (manages .json config files)
config_manager = ConfigManager(DATA_DIR)
llm_tool_collection = LLMToolCollection(TOOLS_DIR, DATA_DIR, config_manager, llm_service)

# ==============================================================================
# 6. LIFESPAN (STARTUP / SHUTDOWN)
# ==============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle.
    - Startup: Loads the configured model once into VRAM.
    - Shutdown: Frees VRAM memory and performs garbage collection.
    
    IMPORTANT: Loading per request would be catastrophically slow performance-wise.
    """
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
        yield  # Application runs here
    except Exception as e:
        logger.error(f"🚨 Error loading model: {e}")
        yield
    finally:
        logger.info("🛑 Shutting down server and clearing VRAM...")
        if llm_service:
            del llm_service
        gc.collect()

# ==============================================================================
# 7. FASTAPI APP INITIALIZATION & MIDDLEWARE
# ==============================================================================
app = FastAPI(
    title="Gemma 4 Chat API",
    description="REST API for local LLM interaction with character routing and JWT auth.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS middleware (for frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==============================================================================

app.include_router(auth.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(system.router)

# 13. APPLICATION ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=HOST,
        port=PORT,
        ssl_keyfile=SSL_KEYFILE,
        ssl_certfile=SSL_CERTFILE,
        timeout_graceful_shutdown=5,
    )