import os
from typing import List, NotRequired, Optional, TypedDict

from chat_exception import ChatException
from repository import Repository


# Default director prompt used for plot generation when a character has
# no custom ``plot_generation_prompt`` configured. The ``${time}`` placeholder is
# substituted with the in-world start time by the agent before the call.
DEFAULT_PLOT_GENERATION_PROMPT = "Du bist ein Director für Rollenspiele. Erstelle einen Plot für den restlichen Tag. Der Plot startet zu folgendem Zeitpunkt: ${time}"

class VirtualClockEntry(TypedDict):
    """Defines the persisted anchor pair for a character's virtual clock.

    ``baseTimestamp`` is the in-world anchor in milliseconds and
    ``anchorTimestamp`` the wall-clock moment that anchor was applied.
    """
    baseTimestamp: int
    anchorTimestamp: int


class CharacterEntry(TypedDict):
    """Defines the structure for a character configuration entry."""
    name: str
    character_name: str
    user_name: str
    system_prompt: str
    intro: NotRequired[str]
    plot_generation_prompt: NotRequired[str]
    sticky_note: NotRequired[str]
    sticky_note_pos: NotRequired[int]
    append_timestamp: bool
    reset_cache: NotRequired[bool]
    full_history_for_last_n: NotRequired[int]
    full_history_for_last_n_plot_generation: NotRequired[int]
    cap_history: NotRequired[int]
    idle_threshold_ms: int
    time_scale: NotRequired[float]
    enable_thinking: NotRequired[bool]
    temperature: NotRequired[float]
    min_p: NotRequired[float]
    top_p: NotRequired[float]
    top_k: NotRequired[int]
    repeat_penalty: NotRequired[float]
    frequency_penalty: NotRequired[float]
    presence_penalty: NotRequired[float]
    max_tokens: NotRequired[int]
    virtual_clock: NotRequired[VirtualClockEntry]


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

    def get_character_name(self, character: str) -> str:
        """Fetch the display name used for the character in the rolling summary.

        The name is optional; when it is not configured the generic
        ``"Assistant"`` label is used so the summary falls back to the previous
        ASSISTANT attribution.
        """
        found = self.get_character_by_name(character)
        return (found.get("character_name") if found else None) or "Assistant"

    def get_user_name(self, character: str) -> str:
        """Fetch the display name used for the user in the rolling summary.

        The name is optional; when it is not configured the generic ``"User"``
        label is used so the summary falls back to the previous USER attribution.
        """
        found = self.get_character_by_name(character)
        return (found.get("user_name") if found else None) or "User"

    def get_system_prompt(self, character: str) -> str:
        """Fetch the system prompt associated with a given character."""
        found = self.get_character_by_name(character)
        return found.get("system_prompt", "") if found else ""

    def get_intro(self, character: str) -> str:
        """Fetch the optional narrative intro for a given character."""
        found = self.get_character_by_name(character)
        return found.get("intro", "") if found else ""

    def get_plot_generation_prompt(self, character: str) -> str:
        """Fetch the director prompt used for plot generation.

        This prompt is appended after the chat history to trigger plot
        generation, placing the instruction at the end of the context for
        better recency.

        Falls back to :data:`DEFAULT_PLOT_GENERATION_PROMPT` when the character
        has no custom prompt configured, so existing characters keep their
        previous behaviour without requiring a stored value.
        """
        found = self.get_character_by_name(character)
        if not found:
            return DEFAULT_PLOT_GENERATION_PROMPT
        return found.get("plot_generation_prompt") or DEFAULT_PLOT_GENERATION_PROMPT

    def get_sticky_note(self, character: str) -> str:
        """Fetch the character's sticky note.

        The note is stored as raw text (without ``<director>`` tags) and steers the
        upcoming turns. Returns an empty string when no note is set.
        """
        found = self.get_character_by_name(character)
        return found.get("sticky_note", "") if found else ""

    def set_sticky_note(self, character: str, text: str) -> None:
        """Update or clear the character's sticky note.

        An empty or whitespace-only ``text`` removes the stored note entirely so
        nothing is injected into the context anymore.

        Raises:
            ChatException: When the character does not exist.
        """
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        stripped = text.strip()
        if stripped:
            found["sticky_note"] = stripped
        else:
            found.pop("sticky_note", None)
        self.save_changes()

    def get_sticky_note_pos(self, character: str) -> int:
        """Fetch the sticky note position for a given character.

        The position controls how many *user* messages must follow the injected
        sticky note in the history. ``0`` (the default) makes the note the very
        last entry, which the model follows most reliably; ``1`` places it right
        before the last user message. Any non-negative integer is accepted;
        invalid or missing values fall back to ``0``.
        """
        found = self.get_character_by_name(character)
        if not found:
            return 0
        value = found.get("sticky_note_pos")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return 0

    def get_append_timestamp(self, character: str) -> bool:
        """Fetch the append_timestamp flag for a given character.

        Controls whether a ``<timestamp>`` block is appended to each stored user
        message.
        """
        found = self.get_character_by_name(character)
        return found.get("append_timestamp", False) if found else False

    def get_reset_cache(self, character: str) -> bool:
        """Fetch the reset_cache flag for a given character.

        Controls whether the KV cache is flushed before each inference call.
        Defaults to ``False`` (no reset) when not configured, so the flag is only
        active when explicitly enabled.
        """
        found = self.get_character_by_name(character)
        return found.get("reset_cache", False) if found else False

    def get_full_history_for_last_n(self, character: str) -> Optional[int]:
        """Fetch the number of most recent messages to forward to the LLM in full.

        Returns the configured count, or ``None`` when the character has no
        limit configured, in which case the full history is forwarded.
        """
        return self.__get_history_window_value(character, "full_history_for_last_n")

    def get_full_history_for_last_n_plot_generation(self, character: str) -> Optional[int]:
        """Fetch the number of most recent messages to forward in full for plot generation.

        Plot generation benefits from a larger window than the roleplay itself,
        so this value is configured separately. When it is not configured it
        falls back to the roleplay value from
        :meth:`get_full_history_for_last_n`; ``None`` is only returned when
        neither is configured, in which case the full history is forwarded.
        """
        value = self.__get_history_window_value(character, "full_history_for_last_n_plot_generation")
        if value is not None:
            return value
        return self.get_full_history_for_last_n(character)

    def get_cap_history(self, character: str) -> Optional[int]:
        """Fetch the maximum number of most recent history entries to send to the LLM.

        Unlike :meth:`get_full_history_for_last_n`, which limits how many recent
        messages are forwarded in full, this caps the total number of entries
        (any role) loaded for inference. Returns the configured count, or
        ``None`` when no limit is configured, in which case the full history is
        forwarded.
        """
        return self.__get_history_window_value(character, "cap_history")

    def __get_history_window_value(self, character: str, key: str) -> Optional[int]:
        """Read a non-negative integer history-window setting for a character.

        Shared by the roleplay, plot-generation and cap-history getters; returns
        ``None`` when the character is unknown or the stored value is missing or
        invalid.
        """
        found = self.get_character_by_name(character)
        if not found:
            return None
        value = found.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    def get_idle_threshold_ms(self, character: str) -> int:
        """Fetch the general idle threshold in ms for a given character. Defaults to 1 hour."""
        found = self.get_character_by_name(character)
        return found.get("idle_threshold_ms", 3600000) if found else 3600000

    def get_enable_thinking(self, character: str) -> bool:
        """Fetch the reasoning (thinking) flag for a given character.

        Controls whether the model emits its reasoning output for the
        character's turns. Defaults to ``True`` when not configured.
        """
        found = self.get_character_by_name(character)
        return found.get("enable_thinking", True) if found else True

    def get_time_scale(self, character: str) -> float:
        """Fetch the virtual-clock time scale for a given character.

        The time scale controls how fast the in-world clock advances relative to
        real time. Returns the configured factor, or ``1.0`` (real time) when no
        valid positive value is configured.
        """
        found = self.get_character_by_name(character)
        if not found:
            return 1.0
        value = found.get("time_scale")
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else 1.0

    def get_generation_params(self, character: str) -> dict:
        """Returns a dictionary of configured LLM generation parameters."""
        found = self.get_character_by_name(character)
        if not found:
            return {}
        
        params = {}
        for key in ["temperature", "min_p", "top_p", "top_k", "repeat_penalty", "frequency_penalty", "presence_penalty", "max_tokens"]:
            if key in found and found.get(key) is not None:
                params[key] = found[key]
        return params

    def get_virtual_clock(self, character: str) -> Optional[VirtualClockEntry]:
        """Retrieve the persisted virtual clock anchor for a given character."""
        found = self.get_character_by_name(character)
        return found.get("virtual_clock") if found else None

    def set_virtual_clock(self, character: str, base_timestamp: int, anchor_timestamp: int) -> None:
        """Update or insert the virtual clock anchor for a given character."""
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        found["virtual_clock"] = {
            "baseTimestamp": base_timestamp,
            "anchorTimestamp": anchor_timestamp,
        }
        self.save_changes()

    def clear_virtual_clock(self, character: str) -> bool:
        """Remove the stored virtual clock anchor for a given character.

        Returns True when an anchor was removed, False when none existed.
        Raises ChatException when the character does not exist.
        """
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        if "virtual_clock" not in found:
            return False

        del found["virtual_clock"]
        self.save_changes()
        return True

    def insert_character(
        self,
        name: str,
        character_name: str = "",
        user_name: str = "",
        system_prompt: str = "",
        intro: str = "",
        plot_generation_prompt: str = "",
        sticky_note: str = "",
        sticky_note_pos: Optional[int] = None,
        append_timestamp: bool = False,
        reset_cache: bool = False,
        full_history_for_last_n: Optional[int] = None,
        full_history_for_last_n_plot_generation: Optional[int] = None,
        cap_history: Optional[int] = None,
        idle_threshold_ms: int = 3600000,
        time_scale: Optional[float] = None,
        temperature: Optional[float] = None,
        min_p: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        """Add a new character configuration to the repository."""
        if self.get_character_by_name(name) is not None:
            return

        entry: CharacterEntry = {
            "name": name,
            "character_name": character_name.strip(),
            "user_name": user_name.strip(),
            "system_prompt": system_prompt.strip(),
            "append_timestamp": append_timestamp,
            "idle_threshold_ms": idle_threshold_ms,
        }

        # Only persisted when enabled so the default (no cache reset) stays absent.
        if reset_cache:
            entry["reset_cache"] = True

        if full_history_for_last_n is not None and full_history_for_last_n >= 0:
            entry["full_history_for_last_n"] = full_history_for_last_n
        if full_history_for_last_n_plot_generation is not None and full_history_for_last_n_plot_generation >= 0:
            entry["full_history_for_last_n_plot_generation"] = full_history_for_last_n_plot_generation
        if cap_history is not None and cap_history >= 0:
            entry["cap_history"] = cap_history
        if time_scale is not None and time_scale > 0:
            entry["time_scale"] = time_scale
        if intro:
            entry["intro"] = intro.strip()
        if plot_generation_prompt:
            entry["plot_generation_prompt"] = plot_generation_prompt.strip()
        if sticky_note:
            entry["sticky_note"] = sticky_note.strip()
        if sticky_note_pos is not None and sticky_note_pos >= 0:
            entry["sticky_note_pos"] = sticky_note_pos
        if temperature is not None:
            entry["temperature"] = temperature
        if min_p is not None:
            entry["min_p"] = min_p
        if top_p is not None:
            entry["top_p"] = top_p
        if top_k is not None:
            entry["top_k"] = top_k
        if repeat_penalty is not None:
            entry["repeat_penalty"] = repeat_penalty
        if frequency_penalty is not None:
            entry["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            entry["presence_penalty"] = presence_penalty
        if max_tokens is not None:
            entry["max_tokens"] = max_tokens

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

        generation_params = ["temperature", "min_p", "top_p", "top_k", "repeat_penalty", "frequency_penalty", "presence_penalty", "max_tokens"]

        for key, value in kwargs.items():
            if key in ("character_name", "user_name") and value is not None:
                found[key] = value.strip()
            elif key == "system_prompt" and value is not None:
                found["system_prompt"] = value.strip()
            elif key == "intro" and value is not None:
                # Empty strings clear the intro instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["intro"] = stripped
                else:
                    found.pop("intro", None)
            elif key == "plot_generation_prompt" and value is not None:
                # Empty strings clear the custom prompt so plot generation falls
                # back to DEFAULT_PLOT_GENERATION_PROMPT instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["plot_generation_prompt"] = stripped
                else:
                    found.pop("plot_generation_prompt", None)
            elif key == "sticky_note" and value is not None:
                # Empty strings clear the note so nothing is injected anymore
                # instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["sticky_note"] = stripped
                else:
                    found.pop("sticky_note", None)
            elif key == "sticky_note_pos":
                # ``None`` or negative values clear the position so it falls back
                # to the default of 1 (note before the last user message).
                if value is not None and value >= 0:
                    found[key] = value
                else:
                    found.pop(key, None)
            elif key == "reset_cache":
                # Only stored when enabled so the disabled default stays absent.
                if value:
                    found[key] = True
                else:
                    found.pop(key, None)
            elif key in ["append_timestamp", "idle_threshold_ms", "enable_thinking"]:
                if value is not None:
                    found[key] = value
            elif key == "time_scale":
                # ``None`` or non-positive values reset the scale to the default
                # 1.0 (real time) by removing the stored value.
                if value is not None and value > 0:
                    found[key] = value
                else:
                    found.pop(key, None)
            elif key in ("full_history_for_last_n", "full_history_for_last_n_plot_generation", "cap_history"):
                # ``None`` or negative values clear the limit so the full
                # history is forwarded again.
                if value is not None and value >= 0:
                    found[key] = value
                else:
                    found.pop(key, None)
            elif key in generation_params:
                if value is not None:
                    found[key] = value
                else:
                    found.pop(key, None)

        self.save_changes()

    def set_system_prompt(self, character: str, content: str) -> None:
        """Convenience method to update only the system prompt for a character."""
        self.set_character_settings(character=character, system_prompt=content)

    def set_intro(self, character: str, content: str) -> None:
        """Convenience method to update only the intro for a character."""
        self.set_character_settings(character=character, intro=content)

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