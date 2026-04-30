import os
from typing import Dict

from chat_exception import ChatException
from repository import Repository


class CharacterRepository(Repository):
    """Manages persistence and retrieval of character data for a specific user."""

    def __init__(self, data_dir: str, user: str) -> None:
        super().__init__(data_dir, f"{self.encode_filename_part(user)}_characters.json")
        self.user = user

    def get_character_by_name(self, character: str) -> Dict | None:
        """Retrieve a character dictionary by name."""
        return next((c for c in self.data if c.get("name") == character), None)

    def get_system_prompt(self, character: str) -> str:
        """Fetch the system prompt for a given character."""
        found = self.get_character_by_name(character)
        return found.get("system_prompt", "") if found else ""

    def get_send_with_timestamp(self, character: str) -> bool:
        """Fetch the send_with_timestamp flag for a given character."""
        found = self.get_character_by_name(character)
        return found.get("send_with_timestamp", False) if found else False

    def insert_character(
        self,
        name: str,
        system_prompt: str = "",
        send_with_timestamp: bool = False,
    ) -> None:
        """Add a new character to the repository."""
        if self.get_character_by_name(name) is not None:
            return

        self.data.append(
            {
                "name": name,
                "system_prompt": system_prompt.strip(),
                "send_with_timestamp": send_with_timestamp,
            }
        )
        self.save_changes()

    def set_character_settings(
        self,
        character: str,
        system_prompt: str | None = None,
        send_with_timestamp: bool | None = None,
    ) -> None:
        """Update specific settings for an existing character."""
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        if system_prompt is not None:
            found["system_prompt"] = system_prompt.strip()

        if send_with_timestamp is not None:
            found["send_with_timestamp"] = send_with_timestamp

        self.save_changes()

    def set_system_prompt(self, character: str, content: str) -> None:
        """Convenience method to update only the system prompt."""
        self.set_character_settings(character=character, system_prompt=content)

    def delete_character(self, name: str) -> bool:
        """Remove a character and its associated chat history file."""
        initial_len = len(self.data)
        self.data = [c for c in self.data if c.get("name") != name]

        if len(self.data) < initial_len:
            self.save_changes()

            chat_file = f"{self.user}_{name}.json"
            if os.path.exists(chat_file):
                os.remove(chat_file)

            return True
        return False