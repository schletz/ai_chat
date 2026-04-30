from datetime import datetime
import os
import random
from typing import Callable, List

from config_manager import ConfigManager
from llm_service import LLMService


def llm_tool(func: Callable) -> Callable:
    """Decorator to mark methods as usable tools for the LLM."""
    func.is_llm_tool = True
    return func


class BaseTool:
    """Base class for all LLM tools. Provides helper functions and access to core dependencies."""

    def __init__(self, data_dir: str, config_manager: ConfigManager, llm_service: LLMService):
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.llm_service = llm_service

    @llm_tool
    def get_date(self) -> str:
        """
        Returns the current local date and time as a formatted string in the form "Weekday, YYYY-MM-DD HH:MM" (24-hour clock), for example "Sunday, 2026-09-06 14:35".
        Use this tool whenever you need to know the current date, day of the week, or time – for example to decide whether it is a weekend, morning or evening,
        or to check whether a date has already passed.
        Do not assume or guess the current date or time from memory; always call this tool to obtain it.
        The returned value reflects the moment of the call, so call it again if a later step depends on a fresh timestamp.
        This tool takes no arguments.
        """
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        now = datetime.now()
        day_name = days[now.weekday()]
        time_string = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"
        return time_string

    @llm_tool
    def get_random(self, max_value: int) -> int:
        """
        Returns a uniformly distributed random integer between 1 and max_value (both inclusive).

        Use this tool to pick one option at random from a set of alternatives, or whenever
        a decision should be made by chance rather than by reasoning.

        Workflow:
        1. List all possible options and number them consecutively starting at 1
        (e.g. 1 = go swimming, 2 = stay at home, 3 = go out for dinner).
        2. Call this tool with max_value set to the number of options.
        3. Choose the option whose number matches the returned value and act on it.

        Do not pick, guess or invent a number yourself; always call this tool to obtain it.
        Each call produces a new, independent result, so call it once per decision.

        Args:
            max_value: The upper bound of the range (inclusive). When choosing between
                options, this must equal the total number of options. Must be at least 1.

        Returns:
            A random integer between 1 and max_value (inclusive).
        """
        if max_value < 1:
            raise ValueError("max_value must be at least 1")
        return random.randint(1, max_value)

    @llm_tool
    def get_yes_no(self) -> str:
        """
        Returns either "YES" or "NO", chosen at random with equal probability (50/50).
        Use this tool whenever a binary decision should be made randomly rather than by reasoning – for example when the instructions say something like
        "if the answer is YES, do X, otherwise do Y".
        Call the tool first, then act on the returned value exactly as the instructions specify.
        Do not decide or guess the outcome yourself; always call this tool to obtain it.
        Each call produces a new, independent result, so call it once per decision.
        This tool takes no arguments.
        """
        return random.choice(["yes", "no"])

    def _get_random_lines(self, filename: str, count: int) -> List[str]:
        """Reads a file and returns a list of randomly selected lines."""
        with open(os.path.join(self.data_dir, filename), "r", encoding="utf-8") as f:
            lines = f.readlines()
            result = [random.choice(lines).strip() for _ in range(count)]
            return result