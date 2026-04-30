import os
from typing import List, NotRequired, Optional, TypedDict

from chat_exception import ChatException
from repository import Repository


class SummaryEntry(TypedDict):
    """Defines the structure for a generated chat history summary."""
    text: str
    timestamp: int


class CharacterEntry(TypedDict):
    """Defines the structure for a character configuration entry."""
    name: str
    system_prompt: str
    intro: NotRequired[str]
    plot: NotRequired[str]
    send_with_timestamp: bool
    idle_threshold_ms: int
    temperature: NotRequired[float]
    min_p: NotRequired[float]
    top_p: NotRequired[float]
    repeat_penalty: NotRequired[float]
    max_tokens: NotRequired[int]
    auto_summarize_tokens: NotRequired[int]
    summary: NotRequired[SummaryEntry]


class CharacterRepository(Repository):
    """Manages persistence and retrieval of character data for a specific user."""

    def __init__(self, data_dir: str, user: str) -> None:
        super().__init__(data_dir, f"{self.encode_filename_part(user)}_characters.json")
        self.user = user

    def get_characters(self) -> List[str]:
        """Retrieve a list of all registered character names."""
        return [entry.get("name") for entry in self.data]

    def get_character_by_name(self, character: str) -> Optional[CharacterEntry]:
        """Retrieve the full configuration dictionary for a specific character."""
        return next((c for c in self.data if c.get("name") == character), None)

    def get_system_prompt(self, character: str) -> str:
        """Fetch the system prompt associated with a given character."""
        found = self.get_character_by_name(character)
        return found.get("system_prompt", "") if found else ""

    def get_intro(self, character: str) -> str:
        """Fetch the optional narrative intro for a given character."""
        found = self.get_character_by_name(character)
        return found.get("intro", "") if found else ""

    def get_plot(self, character: str) -> str:
        """Fetch the optional daily plot for a given character."""
        found = self.get_character_by_name(character)
        return found.get("plot", "") if found else ""

    def get_send_with_timestamp(self, character: str) -> bool:
        """Fetch the send_with_timestamp flag for a given character."""
        found = self.get_character_by_name(character)
        return found.get("send_with_timestamp", False) if found else False

    def get_idle_threshold_ms(self, character: str) -> int:
        """Fetch the general idle threshold in ms for a given character. Defaults to 1 hour."""
        found = self.get_character_by_name(character)
        return found.get("idle_threshold_ms", 3600000) if found else 3600000

    def get_auto_summarize_tokens(self, character: str) -> Optional[int]:
        """Fetch the auto summarize token threshold for a given character.

        Returns the configured threshold or ``None`` when the character has no
        threshold configured, in which case automatic summarization should be
        skipped entirely.
        """
        found = self.get_character_by_name(character)
        if not found:
            return None
        value = found.get("auto_summarize_tokens")
        return value if isinstance(value, int) and value > 0 else None

    def get_generation_params(self, character: str) -> dict:
        """Returns a dictionary of configured LLM generation parameters."""
        found = self.get_character_by_name(character)
        if not found:
            return {}
        
        params = {}
        for key in ["temperature", "min_p", "top_p", "repeat_penalty", "max_tokens"]:
            if key in found and found.get(key) is not None:
                params[key] = found[key]
        return params

    def get_summary(self, character: str) -> Optional[SummaryEntry]:
        """Retrieve the current chat summary for a given character."""
        found = self.get_character_by_name(character)
        return found.get("summary") if found else None

    def set_summary(self, character: str, text: str, timestamp: int) -> None:
        """Update or insert the chat history summary for a given character."""
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        found["summary"] = {
            "text": text,
            "timestamp": timestamp
        }
        self.save_changes()

    def clear_summary(self, character: str) -> bool:
        """Remove the stored chat summary for a given character.

        Returns True when a summary was removed, False when no summary existed.
        Raises ChatException when the character does not exist.
        """
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        if "summary" not in found:
            return False

        del found["summary"]
        self.save_changes()
        return True

    def insert_character(
        self,
        name: str,
        system_prompt: str = "",
        intro: str = "",
        plot: str = "",
        send_with_timestamp: bool = False,
        idle_threshold_ms: int = 3600000,
        temperature: Optional[float] = None,
        min_p: Optional[float] = None,
        top_p: Optional[float] = None,
        repeat_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
        auto_summarize_tokens: Optional[int] = None,
    ) -> None:
        """Add a new character configuration to the repository."""
        if self.get_character_by_name(name) is not None:
            return

        entry: CharacterEntry = {
            "name": name,
            "system_prompt": system_prompt.strip(),
            "send_with_timestamp": send_with_timestamp,
            "idle_threshold_ms": idle_threshold_ms,
        }

        if intro:
            entry["intro"] = intro.strip()
        if plot:
            entry["plot"] = plot.strip()
        if temperature is not None:
            entry["temperature"] = temperature
        if min_p is not None:
            entry["min_p"] = min_p
        if top_p is not None:
            entry["top_p"] = top_p
        if repeat_penalty is not None:
            entry["repeat_penalty"] = repeat_penalty
        if max_tokens is not None:
            entry["max_tokens"] = max_tokens
        if auto_summarize_tokens is not None:
            entry["auto_summarize_tokens"] = auto_summarize_tokens

        self.data.append(entry)
        self.save_changes()

    def set_character_settings(
        self,
        character: str,
        **kwargs
    ) -> None:
        """Update specific configuration settings for an existing character."""
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        generation_params = ["temperature", "min_p", "top_p", "repeat_penalty", "max_tokens"]

        for key, value in kwargs.items():
            if key == "system_prompt" and value is not None:
                found["system_prompt"] = value.strip()
            elif key == "intro" and value is not None:
                # Empty strings clear the intro instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["intro"] = stripped
                else:
                    found.pop("intro", None)
            elif key == "plot" and value is not None:
                # Empty strings clear the plot instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["plot"] = stripped
                else:
                    found.pop("plot", None)
            elif key in ["send_with_timestamp", "idle_threshold_ms"]:
                if value is not None:
                    found[key] = value
            elif key in generation_params:
                if value is not None:
                    found[key] = value
                else:
                    found.pop(key, None)
            elif key == "auto_summarize_tokens":
                # ``None`` or non-positive values disable automatic summarization
                # by removing the stored threshold entirely.
                if value is not None and value > 0:
                    found[key] = value
                else:
                    found.pop(key, None)

        self.save_changes()

    def set_system_prompt(self, character: str, content: str) -> None:
        """Convenience method to update only the system prompt for a character."""
        self.set_character_settings(character=character, system_prompt=content)

    def delete_character(self, name: str) -> bool:
        """Remove a character configuration and its associated chat history file."""
        initial_len = len(self.data)
        # Filter out the target character to update state
        self.data = [c for c in self.data if c.get("name") != name]

        if len(self.data) < initial_len:
            self.save_changes()

            chat_file = f"{self.user}_{name}.json"
            if os.path.exists(chat_file):
                os.remove(chat_file)

            return True
        return False