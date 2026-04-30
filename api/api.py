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
import jwt
import uvicorn

from typing import Optional
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Local Modules
from character_agent import CharacterAgent
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from config_manager import ConfigManager
from llm_service import LLMService
from tool_collection import LLMToolCollection
from user_repository import UserRepository


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
# 5. PYDANTIC SCHEMAS
# ==============================================================================
class AuthRequest(BaseModel):
    """Request for user authentication."""
    username: str
    password: str


class CharacterCreate(BaseModel):
    """Schema for creating a new character."""
    name: str
    system_prompt: str
    send_with_timestamp: bool = True


class ChatMessage(BaseModel):
    """Schema for a chat message to be sent."""
    message: str


class CharacterUpdate(BaseModel):
    """Schema for updating existing character settings."""
    system_prompt: Optional[str] = None
    send_with_timestamp: Optional[bool] = None


class ModelChangeRequest(BaseModel):
    """Request for switching the active LLM model."""
    model_id: str


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
# 8. AUTHENTICATION HELPER & DEPENDENCIES
# ==============================================================================
def create_access_token(data: dict) -> str:
    """
    Creates a JWT with an expiration time (24 hours).
    Uses 'sub' as the standard field for the username.
    """
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(request: Request) -> str:
    """
    FastAPI Dependency: Extracts and validates the JWT from HttpOnly cookies.
    Returns the username on success, otherwise raises a 401 HTTPException.
    
    Developer Note: 
    - secure=True & samesite="none" are required for cross-origin cookie transmission.
    - httponly=True protects against XSS attacks on the token.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid or expired"
        )


# ==============================================================================
# 9. ROUTES: AUTHENTICATION & CERTIFICATES
# ==============================================================================
@app.get("/accept-cert")
async def accept_certificate(redirectUrl: str):
    """
    Triggers browser certificate warnings (HTTPS/SSL).
    Redirects to the target URL with a query parameter after acceptance.
    """
    separator = "&" if "?" in redirectUrl else "?"
    final_url = f"{redirectUrl}{separator}certificateAccepted=true"
    return Response(status_code=status.HTTP_302_FOUND, headers={"Location": final_url})


@app.post("/users/auth")
async def authenticate_user(req: AuthRequest, response: Response):
    """User login. Validates credentials and sets JWT cookie."""
    user_repo = UserRepository(DATA_DIR)

    if not user_repo.authenticate(req.username, req.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password"
        )

    access_token = create_access_token(data={"sub": req.username})
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=24 * 60 * 60,  # 24 hours
    )
    return {"message": "Successfully logged in"}


@app.post("/users/logout")
async def logout(response: Response):
    """Deletes the JWT cookie and ends the session on the client side."""
    response.delete_cookie(key="access_token", secure=True, samesite="none", httponly=True)
    return {"message": "Successfully logged out"}


# ==============================================================================
# 10. ROUTES: CHARACTER MANAGEMENT
# ==============================================================================
@app.get("/characters")
async def get_characters(username: str = Depends(get_current_user)):
    """Lists all characters for the authenticated user."""
    char_repo = CharacterRepository(DATA_DIR, username)
    return {"characters": char_repo.data}


@app.post("/characters", status_code=status.HTTP_201_CREATED)
async def create_character(char: CharacterCreate, username: str = Depends(get_current_user)):
    """Creates a new character. Checks for duplicates."""
    char_repo = CharacterRepository(DATA_DIR, username)
    if char_repo.get_character_by_name(char.name) is not None:
        raise HTTPException(status_code=400, detail="Character already exists")

    char_repo.insert_character(
        char.name,
        char.system_prompt,
        char.send_with_timestamp,
    )
    return {"message": f"Character {char.name} created."}


@app.put("/characters/{name}")
async def update_character(
    name: str, update_data: CharacterUpdate, username: str = Depends(get_current_user)
):
    """Updates system prompt or timestamp setting of a character."""
    char_repo = CharacterRepository(DATA_DIR, username)
    try:
        char_repo.set_character_settings(
            character=name,
            system_prompt=update_data.system_prompt,
            send_with_timestamp=update_data.send_with_timestamp,
        )
        return {"message": f"Character {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/characters/{name}")
async def delete_character(name: str, username: str = Depends(get_current_user)):
    """Deletes a character and its associated data."""
    char_repo = CharacterRepository(DATA_DIR, username)
    if char_repo.delete_character(name):
        return {"message": f"Character {name} successfully deleted."}
    raise HTTPException(status_code=404, detail="Character not found.")


# ==============================================================================
# 11. ROUTES: CHAT MANAGEMENT
# ==============================================================================
@app.get("/characters/{name}/chat")
async def get_chat(
    name: str, 
    fromTimestamp: int = 0, 
    username: str = Depends(get_current_user)
):
    """Retrieves chat history. Optionally with timestamp filter for incremental loading."""
    char_repo = CharacterRepository(DATA_DIR, username)
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo = ChatRepository(DATA_DIR, username, name)
    agent = CharacterAgent(char_repo, chat_repo, llm_service, llm_tool_collection)

    history = agent.get_frontend_chat_history()
    if fromTimestamp > 0:
        history = [msg for msg in history if msg.get("timestamp", 0) >= fromTimestamp]
    return history


@app.post("/characters/{name}/chat", status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    name: str, chat_msg: ChatMessage, username: str = Depends(get_current_user)
):
    """Sends a message to the character and generates a response via LLM."""
    char_repo = CharacterRepository(DATA_DIR, username)
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found")

    chat_repo = ChatRepository(DATA_DIR, username, name)
    agent = CharacterAgent(char_repo, chat_repo, llm_service, llm_tool_collection)

    # IMPORTANT: asyncio.to_thread prevents blocking the event loop during GPU inference.
    async with llm_lock:
        bot_response_text = await asyncio.to_thread(agent.process_user_message, chat_msg.message)

    return {"role": "assistant", "content": bot_response_text}


@app.post("/characters/{name}/chat/recreate", status_code=status.HTTP_201_CREATED)
async def recreate_chat_message(name: str, username: str = Depends(get_current_user)):
    """Deletes the last assistant response and regenerates it (based on the same context)."""
    char_repo = CharacterRepository(DATA_DIR, username)
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo = ChatRepository(DATA_DIR, username, name)
    chat_repo.delete_last_assistant_message()
    
    agent = CharacterAgent(char_repo, chat_repo, llm_service, llm_tool_collection)

    async with llm_lock:
        bot_response_text = await asyncio.to_thread(agent.recreate_last_message)

    return {"role": "assistant", "content": bot_response_text}


@app.delete("/characters/{name}/chat/{timestamp}")
async def delete_chat_message(
    name: str, timestamp: int, username: str = Depends(get_current_user)
):
    """Deletes a specific message from the chat history."""
    chat_repo = ChatRepository(DATA_DIR, username, name)
    if chat_repo.delete_message(timestamp):
        return {"message": "Message deleted."}
    raise HTTPException(status_code=404, detail="Message not found.")


# ==============================================================================
# 12. ROUTES: SYSTEM & MODEL MANAGEMENT
# ==============================================================================
@app.get("/system/models")
async def get_system_models(username: str = Depends(get_current_user)):
    """Returns available models and the currently active ID (for frontend dropdowns)."""
    return {
        "active_model_id": config_manager.get_active_model_id(),
        "models": config_manager.get_available_models(),
    }


@app.post("/system/model")
async def change_model(req: ModelChangeRequest, username: str = Depends(get_current_user)):
    """Switches the active LLM model. Triggers a controlled server restart."""
    config = config_manager.get_config()
    models = config.get("models", [])

    # 1. Security & Validity Check
    if not any(m.get("id") == req.model_id for m in models):
        raise HTTPException(status_code=404, detail="Model ID not found")

    # 2. Update configuration
    config["active_model_id"] = req.model_id
    config_manager.save_config(config)

    logger.info(f"🔄 Model switch requested for ID: {req.model_id}. Server restarting...")

    # 3. Controlled shutdown in background thread
    # time.sleep(1) ensures the HTTP response (200 OK) reaches the frontend.
    # _thread.interrupt_main() simulates KeyboardInterrupt in the main process.
    def delayed_shutdown():
        time.sleep(1)
        _thread.interrupt_main()

    threading.Thread(target=delayed_shutdown, daemon=True).start()

    return {"message": "Model saved. Server will restart in a few seconds."}


# ==============================================================================
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