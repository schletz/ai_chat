import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_config_manager, get_llm_service, get_llm_lock
from config_manager import ConfigManager
from llm_service import LLMService
from schemas import ModelChangeRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system")


@router.get("/models")
async def get_system_models(
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Retrieve available models and the currently active model ID."""
    return {
        "active_model_id": config_manager.get_active_model_id(),
        "models": config_manager.get_available_models(),
    }


@router.post("/model")
async def change_model(
    req: ModelChangeRequest,
    config_manager: ConfigManager = Depends(get_config_manager)
):
    """Switch the active LLM model and trigger a controlled server restart."""
    config = config_manager.get_config()
    models = config.get("models", [])

    target_model = next((m for m in models if m.get("id") == req.model_id), None)
    if target_model is None:
        raise HTTPException(status_code=404, detail="Model ID not found")

    config["active_model_id"] = req.model_id
    if req.n_gpu_layers is not None:
        target_model["n_gpu_layers"] = req.n_gpu_layers
    config_manager.save_config(config)

    logger.info(f"Model switch requested for ID: {req.model_id}. Server restarting...")

    # Delay shutdown to ensure the HTTP response reaches the client before termination.
    def delayed_shutdown():
        time.sleep(1)
        # Force-kill the whole process via the OS. A cooperative interrupt is
        # unreliable here because ongoing inference runs in native code and
        # does not react to a KeyboardInterrupt in time. The surrounding
        # launcher script restarts the server automatically afterwards.
        pid = os.getpid()
        if sys.platform == "win32":
            subprocess.Popen(
                ["taskkill", "/F", "/PID", str(pid)],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            # SIGKILL cannot be caught or ignored, mirroring taskkill /F.
            os.kill(pid, signal.SIGKILL)

    threading.Thread(target=delayed_shutdown, daemon=True).start()

    return {"message": "Model saved. Server will restart in a few seconds."}


@router.post("/reset-cache")
async def reset_kv_cache(
    llm_service: LLMService = Depends(get_llm_service),
    llm_lock: asyncio.Lock = Depends(get_llm_lock),
):
    """Clear the model's KV cache and reset its internal state.

    Acquires the LLM lock so the reset never races with an in-flight inference
    call, which would otherwise corrupt the shared model state.
    """
    async with llm_lock:
        llm_service.reset()

    logger.info("KV cache cleared on request.")
    return {"message": "KV cache cleared."}