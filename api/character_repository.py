import os
from typing import Dict

from chat_exception import ChatException
from repository import Repository


# Implements the Repository Pattern specifically for Character domains.
# Encapsulates all data access logic, hiding the underlying file-system operations
# from the business logic layer (CharacterAgent).
class CharacterRepository(Repository):
    def __init__(self, data_dir: str, user: str):
        super().__init__(data_dir, f"{self.encode_filename_part(user)}_characters.json")
        self.user = user

    def get_character_by_name(self, character: str) -> Dict | None:
        return next((c for c in self.data if c.get("name") == character), None)

    def get_system_prompt(self, character: str) -> str:
        found = self.get_character_by_name(character)
        return found.get("system_prompt", "") if found else ""

    def get_send_with_timestamp(self, character: str) -> bool:
        found = self.get_character_by_name(character)
        return found.get("send_with_timestamp", False) if found else False

    def insert_character(
        self,
        name: str,
        system_prompt: str = "",
        send_with_timestamp: bool = False,
    ) -> None:
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
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        if system_prompt is not None:
            found["system_prompt"] = system_prompt.strip()

        if send_with_timestamp is not None:
            found["send_with_timestamp"] = send_with_timestamp

        self.save_changes()

    def set_system_prompt(self, character: str, content: str) -> None:
        self.set_character_settings(character=character, system_prompt=content)

    def delete_character(self, name: str) -> bool:
        # Implements a cascading delete strategy. When a character entity is removed,
        # its associated chat state file is also purged to maintain data integrity
        # and prevent orphaned records on the disk.
        initial_len = len(self.data)
        self.data = [c for c in self.data if c.get("name") != name]

        if len(self.data) < initial_len:
            self.save_changes()

            chat_file = f"{self.user}_{name}.json"
            if os.path.exists(chat_file):
                os.remove(chat_file)

            return True
        return False
