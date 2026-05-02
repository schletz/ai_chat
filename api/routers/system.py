import threading
import time
import _thread
import logging
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_config_manager, get_current_user
from config_manager import ConfigManager
from schemas import ModelChangeRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system")

@router.get("/models")
async def get_system_models(
    config_manager: ConfigManager = Depends(get_config_manager),
    username: str = Depends(get_current_user)
):
    """Returns available models and the currently active ID (for frontend dropdowns)."""
    return {
        "active_model_id": config_manager.get_active_model_id(),
        "models": config_manager.get_available_models(),
    }

@router.post("/model")
async def change_model(
    req: ModelChangeRequest,
    config_manager: ConfigManager = Depends(get_config_manager),
    username: str = Depends(get_current_user)
):
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
