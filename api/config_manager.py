import json
import os
from typing import List, NotRequired, Optional, TypedDict


class ModelConfig(TypedDict):
    """Schema for a single model entry in the system configuration."""

    id: str
    file_path: str
    n_ctx: int
    n_gpu_layers: NotRequired[int]


class SystemConfig(TypedDict):
    """Schema for the full persisted system configuration."""

    active_model_id: str
    models: List[ModelConfig]


class ConfigManager:
    """Central class for managing system configuration.

    Safely reads and writes settings to a JSON file to ensure persistence across server restarts.
    """
    def __init__(self, data_dir: str):
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        self.config_file = os.path.join(data_dir, "system_config.json")
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Initializes the configuration file with default values if it does not exist."""
        if not os.path.exists(self.config_file):
            initial_model_path = os.getenv("MODEL_PATH", "")
            default_config: SystemConfig = {
                "active_model_id": "default",
                "models": [
                    {
                        "id": "default",
                        "file_path": initial_model_path,
                        "n_ctx": 32768,
                    }
                ],
            }
            self.save_config(default_config)

    def get_config(self) -> SystemConfig:
        """Reads and returns the current configuration from disk."""
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, config: SystemConfig) -> None:
        """Writes the provided configuration dictionary to disk."""
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def get_available_models(self) -> List[ModelConfig]:
        """Retrieves the list of available models from the configuration."""
        return self.get_config().get("models", [])

    def get_active_model_id(self) -> str:
        """Retrieves the ID of the currently active model."""
        return self.get_config().get("active_model_id", "")

    def get_active_model_data(self) -> Optional[ModelConfig]:
        """Retrieves the complete dictionary of the active model."""
        config = self.get_config()
        active_id = config.get("active_model_id")

        for model in config.get("models", []):
            if model.get("id") == active_id:
                return model
        return None