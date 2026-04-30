from datetime import datetime
import os
import random
from typing import Callable, List

from config_manager import ConfigManager
from llm_service import LLMService


# Der Decorator bleibt unverändert
def llm_tool(func: Callable) -> Callable:
    func._is_llm_tool = True
    return func


class BaseTool:
    def __init__(self, data_dir: str, config_manager: ConfigManager, llm_service: LLMService):
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.llm_service = llm_service

    @llm_tool
    def get_date(self) -> str:
        """
        Ermittelt den aktuellen Tag und die Uhrzeit
        """
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        now = datetime.now()
        day_name = days[now.weekday()]
        time_string = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"
        return time_string

    def _get_random_lines(self, filename: str, count: int) -> List[str]:
        result = []
        with open(os.path.join(self.data_dir, filename), "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i in range(count):
                result.append(random.choice(lines).strip())
            return result
