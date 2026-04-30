import time
from typing import List, Dict, Optional

from repository import Repository


# Manages the conversational state. In LLM applications, history management is critical
# as language models are inherently stateless; context must be appended dynamically per request.
class ChatRepository(Repository):
    def __init__(self, data_dir: str, user: str, character: str):
        super().__init__(
            data_dir,
            f"{self.encode_filename_part(user)}_{self.encode_filename_part(character)}.json",
        )
        self.user = user
        self.character = character

    def get_chat_history(self) -> List[Dict[str, str]]:
        return self.data

    def add_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> None:
        history = self.data
        now = int(1000 * time.time())
        msg = {"timestamp": now, "role": "assistant", "content": content}

        # Conforming strictly to the OpenAI/LLaMA tool calling specification.
        # When an LLM executes a tool, the specific 'tool_calls' schema must be embedded
        # in the history so the context window recognizes it as a system action, not arbitrary text.
        if tool_calls:
            msg["tool_calls"] = tool_calls

        history.append(msg)
        self.data = history
        self.save_changes()

    def add_user_message(self, content: str) -> None:
        self._add_chat_entry("user", content)

    def add_tool_message(self, content: str, func_name: str, tool_call_id: str) -> None:
        self._add_chat_entry("tool", content, func_name, tool_call_id)

    def add_raw_message(self, content: Dict) -> None:
        self.data.append(content)
        self.save_changes()

    def _add_chat_entry(
        self, role: str, content: str, func_name: str = "", tool_call_id: str = ""
    ) -> None:
        history = self.data if role != "system" else []

        if role == "tool":
            now = int(1000 * time.time())
            history.append(
                {
                    "timestamp": now,
                    "role": "tool",
                    "name": func_name,
                    "content": content,
                    "tool_call_id": tool_call_id,
                }
            )
        else:
            now = int(1000 * time.time())
            history.append({"timestamp": now, "role": role, "content": content})

        self.data = history
        self.save_changes()

    def delete_message(self, timestamp: int) -> bool:
        target_idx = -1

        # 1. Finde den Index der User-Nachricht mit dem gesuchten Timestamp
        for i, msg in enumerate(self.data):
            if msg.get("timestamp") == timestamp:
                target_idx = i
                break

        if target_idx == -1:
            return False

        # 2. Ermittle das Ende des zu löschenden Blocks
        # Wir starten direkt nach der gefundenen Nachricht
        delete_end_idx = target_idx + 1

        # Solange wir nicht am Ende der Liste sind UND die nächste Rolle NICHT "user" ist:
        while delete_end_idx < len(self.data) and self.data[delete_end_idx].get("role") != "user":
            delete_end_idx += 1

        # 3. Lösche den gesamten Block (User-Nachricht + alle folgenden Assistant/Tool-Nachrichten)
        initial_len = len(self.data)
        del self.data[target_idx:delete_end_idx]

        if len(self.data) < initial_len:
            self.save_changes()
            return True

        return False

    def delete_last_assistant_message(self) -> bool:
        if not self.data:
            return False
        last_user_idx = -1
        for i in range(len(self.data) - 1, -1, -1):
            if self.data[i].get("role") == "user":
                last_user_idx = i
                break
        if last_user_idx == len(self.data) - 1:
            return False
        initial_len = len(self.data)
        self.data = self.data[: last_user_idx + 1]

        if len(self.data) < initial_len:
            self.save_changes()
            return True

        return False
