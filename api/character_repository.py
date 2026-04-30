import os
from typing import List, NotRequired, Optional, TypedDict

from chat_exception import ChatException
from repository import Repository


# Default system prompt for the plot generation, used when a character has no
# custom ``plot_generation_system_prompt`` configured. It defines the role of the
# director model; the actual task is sent as user content.
DEFAULT_PLOT_GENERATION_SYSTEM_PROMPT = "Du bist ein Director für Rollenspiele."

# Default content for the plot generation, used when a character has no custom
# ``plot_generation_content`` configured. The agent prepends the context (intro)
# before sending it as user message.
DEFAULT_PLOT_GENERATION_CONTENT = "Erstelle einen Plot für den restlichen Tag."

# Default instruction appended after the compact session context to trigger the
# summary generation when a character has no custom ``summarize_prompt``
# configured. It asks for a faithful recap that lets the roleplay continue
# without the original messages.
DEFAULT_SUMMARIZE_PROMPT = (
    "Du bist ein Protokollant für Rollenspiele. Fasse die obige Chat History so "
    "zusammen, dass das Rollenspiel ohne die ursprünglichen Nachrichten nahtlos "
    "fortgesetzt werden kann.\n\n"
    "Halte dabei fest:\n"
    "- Die beteiligten Personen mit ihren Eigenschaften und ihrem Verhältnis zueinander.\n"
    "- Den bisherigen Handlungsverlauf in chronologischer Reihenfolge.\n"
    "- Getroffene Vereinbarungen, Versprechen und offene Fragen.\n"
    "- Die Situation am Ende der History: Ort, Zeit, Stimmung und was gerade geschieht.\n\n"
    "Schreibe die Zusammenfassung in Englisch, im Präsens und in ganzen Sätzen. "
    "Erfinde nichts dazu und lasse nichts weg, was für die Fortsetzung wichtig ist. "
    "Gib ausschließlich den Text der Zusammenfassung aus, ohne Einleitung, ohne "
    "Überschrift und ohne XML-Tags."
)

# Default system prompt for the "insert as idea" feature, used when a character
# has no custom ``idea_generation_system_prompt`` configured. The result is
# inserted 1:1 as a director message and acted out by the next assistant turn,
# so it must be an instruction (what happens), not the scene itself (how it
# plays out). Without an explicit ban the model tends to invent the current
# situation, which then contradicts the actual chat. Short rule lines keep
# local models (around 30B) on track.
DEFAULT_IDEA_GENERATION_SYSTEM_PROMPT = (
    "You are the director of a roleplay. The roleplay is described in the user message.\n\n"
    "Rules:\n"
    "- You do not know the current situation or what happened so far. Do not "
    "describe or invent past events, the current moment, the place or the mood.\n"
    "- **Be creative:** Stay true to the idea, but add creative details or twists.\n"
    "- Provide several ideas so the LLM can choose the most suitable one.\n"
    "- Write in English\n"
    "- Output ONLY the instruction. No explanations, no headings, no XML tags."
)

# Default content for the "insert as idea" feature, used when a character has no
# custom ``idea_generation_content`` configured. The agent prepends the context
# and appends the user's idea before sending it as user message.
DEFAULT_IDEA_GENERATION_CONTENT = (
    "Turn the user's idea below into plot instructions for the next turns.\n\n"
    "User idea:"
)

# Keys of earlier versions that stored the whole generation prompt as a single
# user message. Their values are kept as the new content fields on load.
LEGACY_PROMPT_KEYS = {
    "plot_generation_prompt": "plot_generation_content",
    "idea_director_prompt": "idea_generation_content",
}

# Custom generation prompts. An empty value is never stored, so the respective
# DEFAULT_* constant applies instead.
GENERATION_PROMPT_KEYS = (
    "plot_generation_system_prompt",
    "plot_generation_content",
    "summarize_prompt",
    "idea_generation_system_prompt",
    "idea_generation_content",
)

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
    # English translations of system_prompt and intro, maintained by the
    # character endpoints whenever the source texts change. Stored separately so
    # inference never has to translate on the fly.
    system_prompt_en: NotRequired[str]
    intro_en: NotRequired[str]
    translate_to_english: NotRequired[bool]
    plot: NotRequired[str]
    plot_generation_system_prompt: NotRequired[str]
    plot_generation_content: NotRequired[str]
    sticky_note: NotRequired[str]
    sticky_note_pos: NotRequired[int]
    summarize_prompt: NotRequired[str]
    idea_generation_system_prompt: NotRequired[str]
    idea_generation_content: NotRequired[str]
    append_timestamp: bool
    full_history_for_last_n: NotRequired[int]
    cap_history: NotRequired[int]
    idle_threshold_ms: int
    time_scale: NotRequired[float]
    enable_thinking: NotRequired[bool]
    answer_count: NotRequired[int]
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
        self.__migrate_legacy_prompts()

    def __migrate_legacy_prompts(self) -> None:
        """Rename generation prompt keys of earlier versions to the content keys.

        Earlier versions sent the whole stored prompt as user message, which is
        exactly what the content field is now, so the value is moved unchanged.
        An already present content value wins over the legacy one.
        """
        changed = False
        for entry in self.data:
            for legacy_key, key in LEGACY_PROMPT_KEYS.items():
                if legacy_key not in entry:
                    continue
                value = entry.pop(legacy_key)
                if value and not entry.get(key):
                    entry[key] = value
                changed = True
        if changed:
            self.save_changes()

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

    def get_translate_to_english(self, character: str) -> bool:
        """Fetch whether inference uses the English system prompt and intro.

        Defaults to ``False`` when not configured, so the original texts are used.
        """
        found = self.get_character_by_name(character)
        return found.get("translate_to_english", False) if found else False

    def get_system_prompt_en(self, character: str) -> str:
        """Fetch the stored English translation of the system prompt.

        Returns an empty string when no translation has been stored yet.
        """
        found = self.get_character_by_name(character)
        return found.get("system_prompt_en", "") if found else ""

    def get_intro_en(self, character: str) -> str:
        """Fetch the stored English translation of the intro.

        Returns an empty string when no translation has been stored yet.
        """
        found = self.get_character_by_name(character)
        return found.get("intro_en", "") if found else ""

    def set_translations(
        self,
        character: str,
        system_prompt_en: Optional[str] = None,
        intro_en: Optional[str] = None,
    ) -> None:
        """Store or clear the English translations of system prompt and intro.

        ``None`` leaves the respective translation untouched, an empty string
        removes it. The data is re-read from disk first: translating takes a
        while, and changes saved by other requests in the meantime (e.g. the
        virtual clock) must not be overwritten by this instance's stale state.

        Raises:
            ChatException: When the character does not exist.
        """
        self.data = self.read_data()
        found = self.get_character_by_name(character)
        if found is None:
            raise ChatException(f"Character {character} not found")

        for key, value in (("system_prompt_en", system_prompt_en), ("intro_en", intro_en)):
            if value is None:
                continue
            stripped = value.strip()
            if stripped:
                found[key] = stripped
            else:
                found.pop(key, None)
        self.save_changes()

    def get_plot(self, character: str) -> str:
        """Fetch the optional plot for a given character.

        The plot is generated by :meth:`character_agent.CharacterAgent.generate_plot`
        and appended to the system prompt. Returns an empty string when no plot
        has been generated or stored yet.
        """
        found = self.get_character_by_name(character)
        return found.get("plot", "") if found else ""

    def get_plot_generation_system_prompt(self, character: str) -> str:
        """Fetch the system prompt used for plot generation.

        Falls back to :data:`DEFAULT_PLOT_GENERATION_SYSTEM_PROMPT` when the
        character has no custom prompt configured.
        """
        return self.__get_prompt(
            character, "plot_generation_system_prompt", DEFAULT_PLOT_GENERATION_SYSTEM_PROMPT
        )

    def get_plot_generation_content(self, character: str) -> str:
        """Fetch the user content that triggers the plot generation.

        The agent places it after the context in the user message, so the
        instruction sits at the end of the input for better recency. Falls back
        to :data:`DEFAULT_PLOT_GENERATION_CONTENT` when the character has no
        custom content configured.
        """
        return self.__get_prompt(
            character, "plot_generation_content", DEFAULT_PLOT_GENERATION_CONTENT
        )

    def get_summarize_prompt(self, character: str) -> str:
        """Fetch the instruction used for the summary generation.

        The prompt is appended after the compact session context to trigger
        the summary. Falls back to :data:`DEFAULT_SUMMARIZE_PROMPT` when the
        character has no custom prompt configured.
        """
        return self.__get_prompt(character, "summarize_prompt", DEFAULT_SUMMARIZE_PROMPT)

    def get_idea_generation_system_prompt(self, character: str) -> str:
        """Fetch the system prompt used to turn a user idea into an instruction.

        Falls back to :data:`DEFAULT_IDEA_GENERATION_SYSTEM_PROMPT` when the
        character has no custom prompt configured.
        """
        return self.__get_prompt(
            character, "idea_generation_system_prompt", DEFAULT_IDEA_GENERATION_SYSTEM_PROMPT
        )

    def get_idea_generation_content(self, character: str) -> str:
        """Fetch the user content used to turn a user idea into an instruction.

        The agent places it between the context and the user's idea. Falls back
        to :data:`DEFAULT_IDEA_GENERATION_CONTENT` when the character has no
        custom content configured.
        """
        return self.__get_prompt(
            character, "idea_generation_content", DEFAULT_IDEA_GENERATION_CONTENT
        )

    def __get_prompt(self, character: str, key: str, default: str) -> str:
        """Read a custom generation prompt, falling back to ``default`` when unset."""
        found = self.get_character_by_name(character)
        return (found.get(key) if found else None) or default

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

    def get_full_history_for_last_n(self, character: str) -> Optional[int]:
        """Fetch the number of most recent messages to forward to the LLM in full.

        Returns the configured count, or ``None`` when the character has no
        limit configured, in which case the full history is forwarded.
        """
        return self.__get_history_window_value(character, "full_history_for_last_n")

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

        Shared by the full-history and cap-history getters; returns
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

    def get_answer_count(self, character: str) -> int:
        """Fetch how many assistant answers are generated per request.

        Each answer is produced by a separate inference run, so tool calls and
        the regular turn logic stay intact for every one of them. Returns ``1``
        when the character has no valid value configured, which reproduces the
        previous single-answer behaviour.
        """
        found = self.get_character_by_name(character)
        if not found:
            return 1
        value = found.get("answer_count")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
            return value
        return 1

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
        plot: str = "",
        plot_generation_system_prompt: str = "",
        plot_generation_content: str = "",
        sticky_note: str = "",
        sticky_note_pos: Optional[int] = None,
        summarize_prompt: str = "",
        idea_generation_system_prompt: str = "",
        idea_generation_content: str = "",
        append_timestamp: bool = False,
        translate_to_english: bool = False,
        full_history_for_last_n: Optional[int] = None,
        cap_history: Optional[int] = None,
        idle_threshold_ms: int = 3600000,
        time_scale: Optional[float] = None,
        answer_count: Optional[int] = None,
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

        # Only persisted when enabled so the default (original texts) stays absent.
        if translate_to_english:
            entry["translate_to_english"] = True

        if full_history_for_last_n is not None and full_history_for_last_n >= 0:
            entry["full_history_for_last_n"] = full_history_for_last_n
        if cap_history is not None and cap_history >= 0:
            entry["cap_history"] = cap_history
        if time_scale is not None and time_scale > 0:
            entry["time_scale"] = time_scale
        if answer_count is not None and answer_count >= 1:
            entry["answer_count"] = answer_count
        if intro:
            entry["intro"] = intro.strip()
        if plot:
            entry["plot"] = plot.strip()
        prompts = {
            "plot_generation_system_prompt": plot_generation_system_prompt,
            "plot_generation_content": plot_generation_content,
            "summarize_prompt": summarize_prompt,
            "idea_generation_system_prompt": idea_generation_system_prompt,
            "idea_generation_content": idea_generation_content,
        }
        for key, value in prompts.items():
            if value and value.strip():
                entry[key] = value.strip()
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
            elif key == "plot" and value is not None:
                # Empty strings clear the plot instead of storing a blank field.
                stripped = value.strip()
                if stripped:
                    found["plot"] = stripped
                else:
                    found.pop("plot", None)
            elif key in GENERATION_PROMPT_KEYS and value is not None:
                # Empty strings clear the custom prompt so generation falls back
                # to the matching DEFAULT_* constant instead of storing a blank
                # field.
                stripped = value.strip()
                if stripped:
                    found[key] = stripped
                else:
                    found.pop(key, None)
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
            elif key == "translate_to_english":
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
            elif key == "answer_count":
                # ``None`` or values below one reset the count to the default of
                # a single answer by removing the stored value.
                if value is not None and value >= 1:
                    found[key] = value
                else:
                    found.pop(key, None)
            elif key in ("full_history_for_last_n", "cap_history"):
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

    def set_plot(self, character: str, content: str) -> None:
        """Convenience method to update only the plot for a character.

        An existing plot is overwritten; an empty string clears it.
        """
        self.set_character_settings(character=character, plot=content)

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