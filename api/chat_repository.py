import time
from typing import List, Dict, Literal, NotRequired, Optional, TypedDict

from repository import Repository


class ChatEntry(TypedDict):
    """A structured dictionary representing a single entry in the chat history."""
    role: Literal["system", "user", "assistant", "tool"]
    timestamp: int
    content: str
    additional_content: Optional[str]
    is_agent: Optional[bool]
    # Virtual timestamp set by the client-side in-world clock. Absent when the
    # client did not provide a base_timestamp for the message.
    virtual_ts: NotRequired[int]


class ChatRepository(Repository):
    """
    Manages chat history state and persistence for a specific user-character pair.

    This class handles loading, saving, and modifying the chat log, which is
    stored as a JSON file. Each instance is scoped to a unique user and character.
    """

    def __init__(self, data_dir: str, user: str, character: str) -> None:
        """
        Initializes the repository for a specific user and character chat.

        Args:
            data_dir: The base directory where data files are stored.
            user: The username.
            character: The character name.
        """
        super().__init__(
            data_dir,
            f"{self.encode_filename_part(user)}_{self.encode_filename_part(character)}.json",
        )
        self.user = user
        self.character = character

    def get_chat_history(self) -> List[ChatEntry]:
        """
        Retrieves the entire chat history.

        Returns:
            A list of chat entry dictionaries.
        """
        return self.data

    def get_last_message(self, role: Literal["user", "assistant", "agent"]) -> Optional[ChatEntry]:
        """
        Retrieves the last message of a specific role from the history.

        This method handles the special 'agent' role by searching for 'user'
        messages that have the 'is_agent' flag set to True.

        Args:
            role: The message role to search for ('user', 'agent', etc.).

        Returns:
            The last matching chat entry dictionary, or None if not found.
        """
        is_agent = False
        if role == "agent":
            role = "user"
            is_agent = True

        for i in range(len(self.data) - 1, -1, -1):
            item = self.data[i]
            if item.get("role", "") == role and item.get("is_agent", False) == is_agent:
                return item
        return None

    def get_last_message_timestamp(self, role: Literal["user", "assistant", "agent"]) -> int:
        """
        Retrieves the timestamp of the last message of a specific role.

        Args:
            role: The message role to search for.

        Returns:
            The timestamp in milliseconds, or 0 if not found.
        """
        last_message = self.get_last_message(role)
        if last_message is None:
            return 0
        return int(last_message.get("timestamp", 0))
    
    def add_assistant_message(self, content: str, tool_calls: Optional[List] = None) -> None:
        """
        Appends an assistant's message to the chat history.

        Args:
            content: The text content of the message.
            tool_calls: An optional list of tool calls made by the assistant.
        """
        history = self.data
        now = int(1000 * time.time())
        msg: Dict = {"timestamp": now, "role": "assistant", "content": content}

        if tool_calls:
            msg["tool_calls"] = tool_calls

        history.append(msg)
        self.data = history
        self.save_changes()

    def add_user_message(
        self,
        content: str,
        additional_content: str = "",
        virtual_ts: Optional[int] = None,
    ) -> None:
        """
        Appends a user's message to the chat history.

        Args:
            content: The primary text content of the user's message.
            additional_content: Optional secondary content for the message.
            virtual_ts: Optional client-supplied virtual timestamp (ms since epoch).
                When provided it is recorded alongside the wall-clock timestamp so the
                UI can display the user's in-world time.
        """
        self.__add_chat_entry("user", content, additional_content, virtual_ts=virtual_ts)

    def add_tool_message(self, content: str, func_name: str, tool_call_id: str) -> None:
        """
        Appends a tool's execution result to the chat history.

        Args:
            content: The output or result from the tool execution.
            func_name: The name of the function that was executed.
            tool_call_id: The unique identifier for the corresponding tool call.
        """
        self.__add_chat_entry("tool", content, "", func_name, tool_call_id)

    def add_agent_message(self, content: str) -> None:
        """
        Appends an agent-authored message to the chat history.

        Note: Agent messages are stored with the 'user' role but are distinguished
        by an 'is_agent' flag.

        Args:
            content: The text content generated by the agent.
        """
        self.__add_chat_entry("agent", content)

    def delete_user_message(self, timestamp: int) -> bool:
        """
        Deletes a message and any subsequent non-user messages.

        This method finds a message by its timestamp and removes it along with
        any following assistant or tool messages, stopping at the next user message.

        Args:
            timestamp: The timestamp of the message to delete.

        Returns:
            True if one or more messages were deleted, False otherwise.
        """
        start_idx = -1
        length = len(self.data)
        for i in range(length - 1, -1, -1):
            message:ChatEntry = self.data[i]
            if message["timestamp"] == timestamp:
                start_idx = i
                break
        if start_idx == -1:
            return False
        
        next_idx = length
        for i in range(start_idx + 1, length, 1):
            message:ChatEntry = self.data[i]
            if message["role"] == "user" and not message["is_agent"]:
                next_idx = i
                break

        del self.data[start_idx:next_idx]
        self.save_changes()
        return True

    def update_message_content(self, timestamp: int, content: str) -> bool:
        """Replaces the textual content of an existing message identified by its timestamp.

        Args:
            timestamp: The timestamp of the message to update.
            content: The new content to store in place of the previous text.

        Returns:
            True if a matching message was updated, False otherwise.
        """
        for message in self.data:
            if message.get("timestamp") == timestamp:
                message["content"] = content
                self.save_changes()
                return True
        return False

    def delete_last_assistant_message(self) -> bool:
        """
        Removes the most recent assistant response block.

        This deletes all messages after the last user message, effectively
        undoing the last turn of the assistant.

        Returns:
            True if messages were deleted, False otherwise.
        """
        start_idx = -1
        for i in range(len(self.data) - 1, -1, -1):
            message:ChatEntry = self.data[i]
            if message["role"] != "user" or message["is_agent"]:
                start_idx = i
                break
        if start_idx == -1:
            return False
        
        del self.data[start_idx:]
        self.save_changes()
        return True

    def __add_chat_entry(
        self, role: str, content: str,
        additional_content: str = "",
        func_name: str = "", tool_call_id: str = "",
        virtual_ts: Optional[int] = None,
    ) -> None:
        """
        A private helper to format and append a new entry to the chat history.

        Args:
            role: The role of the message author (e.g., 'user', 'tool').
            content: The main text content of the message.
            additional_content: Optional secondary content, used for user messages.
            func_name: The function name, used for tool messages.
            tool_call_id: The tool call ID, used for tool messages.
            virtual_ts: Optional virtual timestamp (ms since epoch); only recorded
                for user messages and only when the client supplied one.
        """
        # A system message resets the history, ensuring it's always the first entry.
        history = self.data if role != "system" else []

        now = int(1000 * time.time())
        if role == "tool":
            history.append(
                {
                    "timestamp": now,
                    "role": "tool",
                    "name": func_name,
                    "content": content,
                    "tool_call_id": tool_call_id,
                }
            )
        elif role == "agent":
            # Agent messages are stored with the 'user' role for model compatibility
            # but are flagged internally to distinguish them from actual user input.
            history.append(
                {"timestamp": now, "role": "user", "content": content, "is_agent": True}
            )
        elif role == "user":
            message: Dict = {
                "timestamp": now, "role": "user", "content": content, "is_agent": False
            }
            if len(additional_content) > 0:
                message["additional_content"] = additional_content
            if virtual_ts is not None:
                message["virtual_ts"] = virtual_ts
            history.append(message)
        else:
            history.append(
                {"timestamp": now, "role": role, "content": content, "is_agent": False}
            )

        self.data = history
        self.save_changes()
