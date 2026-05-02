import json
import os
from typing import Dict, List, Optional


class ConfigManager:
    """
    Zentrale Klasse für die Verwaltung der System-Konfiguration.
    Liest und schreibt die Einstellungen sicher in eine JSON-Datei,
    sodass diese auch bei einem Serverneustart erhalten bleiben.
    """
    def __init__(self, data_dir: str):
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        self.config_file = os.path.join(data_dir, "system_config.json")
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        if not os.path.exists(self.config_file):
            # Fallback: Erstelle eine Basis-Config, falls noch keine existiert
            initial_model_path = os.getenv("MODEL_PATH", "")
            default_config = {
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

    def get_config(self) -> dict:
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, config: dict):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    def get_available_models(self) -> List[Dict]:
        return self.get_config().get("models", [])

    def get_active_model_id(self) -> str:
        return self.get_config().get("active_model_id", "")

    def get_active_model_data(self) -> Optional[Dict]:
        """Gibt das komplette Dictionary des aktiven Modells zurück (für den Server-Start)"""
        config = self.get_config()
        active_id = config.get("active_model_id")

        for model in config.get("models", []):
            if model.get("id") == active_id:
                return model
        return None
