import math
import re
import time
from datetime import datetime
from typing import Optional

import regex

from character_repository import CharacterRepository
from chat_repository import ChatEntry, ChatRepository


# Sentinel timestamp carried by the synthetically injected sticky note entry. It
# never collides with the positive wall-clock timestamps of real messages, so the
# frontend can recognize the sticky note bubble and route its deletion to clearing
# the character's sticky_note instead of deleting a stored message.
INJECTED_STICKY_NOTE_TIMESTAMP = -1


class ChatHistory:
    """
    Assembles and mutates the conversation context for a specific character.

    This class is the read/assembly and non-inferencing-write layer on top of the
    persistence repositories. It filters and shapes the raw chat history for LLM
    inference or frontend display, injects the character's sticky note near the
    end of the context, builds the system prompt and timestamp metadata,
    and offers the message-insert operations that do not trigger any inference.

    Inferencing itself stays in :class:`character_agent.CharacterAgent`.
    """

    def __init__(
        self,
        character_repo: CharacterRepository,
        chat_repo: ChatRepository,
    ) -> None:
        """
        Initializes the chat history with its backing repositories.

        Args:
            character_repo: Repository for character data and prompts.
            chat_repo: Repository for the chat log of a specific character.
        """
        self.character_repo = character_repo
        self.chat_repo = chat_repo
        self.character = chat_repo.character

        self.days = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        self.system_prompt = self.character_repo.get_system_prompt(self.character)

    def build_system_prompt(self,
                            include_intro: bool = False,
                            include_summary: bool = False,
        ) -> str:
        """
        Constructs the full system prompt by injecting critical system rules.

        These rules instruct the LLM on how to handle system-provided metadata
        (like XML tags) without exposing them to the user.

        Returns:
            The complete system prompt string.
        """
        prompt = self.system_prompt

        agent_instruction = (
            "\n\n--- IMPORTANT SYSTEM RULES ---\n"
            "Parts of the incoming messages may be enclosed in XML tags "
            "(e.g., <current_time>...</current_time>, <director>...</director>). This "
            "information does NOT come from the user; it is system metadata "
            "provided to give you context. Use this information to make your "
            "responses realistic and context-aware. CRITICAL: Never mention "
            "these XML tags in your own responses, and NEVER generate XML "
            "tags yourself!"
        )

        if include_intro:
            prompt += "\n\n<intro>\n" + self.character_repo.get_intro(self.character).strip() + "\n</intro>"
        if include_summary:
            summary = self.character_repo.get_summary(self.character)
            summary_text = summary["text"].strip() if summary else ""
            if summary_text:
                prompt += "\n\n<summary>\n" + summary_text + "\n</summary>"

        prompt += agent_instruction
        return prompt

    def build_timestamp_metadata(self, base_timestamp: Optional[int] = None, with_elapsed_time: bool = True) -> str:
        """
        Builds the ``<current_time>`` metadata tag for the next turn.

        The tag combines the in-world date and time with a relative hint of how
        much time has elapsed since the last user message, so the model can
        gauge the passage of time.

        Args:
            base_timestamp: Optional virtual time in milliseconds since the epoch.
                When provided it overrides the current system clock. If ``None``
                the system time is used instead.

        Returns:
            The assembled ``<current_time>...</current_time>`` string.
        """
        last_timestamp = self.chat_repo.get_last_message_timestamp("user", include_virtual_ts=True) / 1000
        current_timestamp = base_timestamp / 1000 if base_timestamp is not None else time.time()
        ago_str = ""
        if with_elapsed_time:
            # Elapsed seconds since the last user message; the hint's granularity
            # is coarsened as the gap grows so the model gets a natural-language
            # sense of the pause rather than an exact figure.
            prev_message_ago = current_timestamp - last_timestamp
            if prev_message_ago >= 24 * 3600:
                # A day or more: drop the hint entirely, the absolute date carries it.
                ago_str = ""
            elif prev_message_ago >= 2 * 3600:
                # 2-24 hours: report in hours rounded to the nearest half hour.
                # ``:g`` drops a trailing ".0" so whole hours read as "3" instead of "3.0".
                hours = round(prev_message_ago * 2 / 3600) / 2
                ago_str = f" ({hours:g} hours after last user message)"
            elif prev_message_ago >= 15 * 60:
                # 15 minutes-2 hours: report in minutes rounded to the nearest 15.
                ago_str = f" ({round(prev_message_ago / 15 / 60) * 15} minutes after last user message)"
            elif prev_message_ago >= 90:
                # 90 seconds-15 minutes: report in minutes rounded to the nearest one.
                ago_str = f" ({round(prev_message_ago / 60)} minutes after last user message)"
            elif prev_message_ago >= 0:
                # Under 90 seconds: treat as an immediate reply.
                ago_str = " (immediately after last user message)"

        # Resolve the absolute in-world clock from virtual time when given, else from the system clock.
        now = datetime.fromtimestamp(base_timestamp / 1000) if base_timestamp is not None else datetime.now()
        return f"<current_time>{self.format_in_world_time(now)}{ago_str}</current_time>"

    def format_in_world_time(self, now: datetime) -> str:
        """
        Renders a datetime as the human-readable in-world time string.

        Produces the same format used in the ``<current_time>`` metadata, e.g.
        ``Monday, June 1st, 2026, 2:30 PM (14:30 Uhr)``, so every place that
        surfaces the in-world time to the LLM stays consistent.

        Args:
            now: The datetime to format.

        Returns:
            The formatted weekday, date and time string.
        """
        day_name = self.days[now.weekday()]
        hour = now.strftime('%I').lstrip('0')
        # English ordinal suffix for the day of month (1st, 2nd, 3rd, 4th, ...).
        # 11th-13th are special cases that always use "th".
        if 11 <= now.day % 100 <= 13:
            ordinal_suffix = "th"
        else:
            ordinal_suffix = {1: "st", 2: "nd", 3: "rd"}.get(now.day % 10, "th")
        return (
            f"{day_name}, {now.strftime('%B')} {now.day}{ordinal_suffix}, "
            f"{now.strftime('%Y, ')}{hour}{now.strftime(':%M %p')} ({now.strftime('%H:%M')} Uhr)"
        )

    def get_filtered_chat_history(
        self,
        clean_user_messages: bool = True,
        filter_tools: bool = True,
        filter_agent: bool = True,
        from_timestamp: int = 0,
        cap_history: int | None = None,
    ) -> list[ChatEntry]:
        """
        Filters and cleans the chat history for frontend display or LLM inference.

        This performs only filtering and cleaning; it never injects synthetic
        entries. Use :meth:`get_injected_chat_history` afterwards (typically once
        the history has been compressed) to add the sticky note.

        Args:
            clean_user_messages: If True, removes XML tags from user messages.
            filter_tools: If True, removes tool call and tool response messages.
            filter_agent: If True, removes agent-initiated system messages.
            from_timestamp: Only include messages with a timestamp strictly greater than this value.
            cap_history: When set, only the most recent ``cap_history`` cleaned
                entries are returned, regardless of role. The history is walked
                backwards so processing stops once enough entries are collected,
                avoiding the cost of cleaning the entire log only to discard all
                but its tail. ``None`` returns the full filtered history.

        Returns:
            A list of cleaned message dictionaries suitable for UI rendering or inference.
        """
        if cap_history == 0:
            return []
        raw_history = self.chat_repo.get_chat_history()
        # This regex pattern finds and removes XML-like tags and their content.
        tag_pattern = re.compile(r"<[^>]+>.*<[^>]+>", flags=re.DOTALL)
        # More aggresive pattern for assistant messages.
        # Qwen sends closing XML tags without opening tags.
        assistant_tag_pattern = re.compile(r"^.*(<\/think>|\|>)", flags=re.DOTALL)
        strip_xml_pattern = re.compile(r"<[^>]*>[^<]*<[^>]*>", flags=re.DOTALL)

        def clean_entry(msg: ChatEntry) -> Optional[ChatEntry]:
            """Filters and cleans a single raw entry.

            Returns the cleaned entry, or ``None`` when it is dropped by the
            active filters, falls at or before ``from_timestamp`` or becomes
            empty after cleaning.
            """
            if msg.get("timestamp", 0) <= from_timestamp:
                return None

            role = msg["role"]
            is_agent = msg.get("is_agent", False)
            if filter_tools and role == "assistant" and "tool_calls" in msg:
                return None
            if filter_tools and role == "tool":
                return None
            if filter_agent and is_agent is True:
                return None

            raw_content = msg["content"]

            if role == "assistant":
                if "tool_calls" in msg:
                    clean_content = raw_content
                else:
                    clean_content = assistant_tag_pattern.sub("", raw_content).strip()
                    clean_content = strip_xml_pattern.sub("", clean_content).strip()
            elif role == "user" and not is_agent:
                clean_content = tag_pattern.sub("", raw_content).strip() if clean_user_messages else raw_content
            else:
                clean_content = raw_content

            if len(clean_content) == 0:
                return None

            clean_msg = msg.copy()
            clean_msg["content"] = clean_content
            return clean_msg

        clean_history: list[ChatEntry] = []
        if cap_history is None:
            for msg in raw_history:
                cleaned = clean_entry(msg)
                if cleaned is not None:
                    clean_history.append(cleaned)
        else:
            # Walk backwards and stop as soon as enough entries are collected, so
            # the full log is never cleaned just to keep its tail. The collected
            # tail is reversed back into chronological (oldest-first) order.
            for msg in reversed(raw_history):
                cleaned = clean_entry(msg)
                if cleaned is not None:
                    clean_history.append(cleaned)
                    if len(clean_history) >= cap_history:
                        break
            clean_history.reverse()

        return clean_history

    def get_injected_chat_history(self, history: list[ChatEntry], base_timestamp: int) -> list[ChatEntry]:
        """
        Adds the synthetic context entries to an already filtered history.

        Kept separate from :meth:`get_filtered_chat_history` so the assembly
        order stays explicit: filter, then compress, then inject. Injecting last
        guarantees the sticky note is positioned relative to the messages that
        are actually sent and is never dropped by the compression step.

        Currently the only injected entry is the character's sticky note. The
        passed list is mutated in place and returned for convenience.

        Args:
            history: The already filtered (and usually compressed) history.
            base_timestamp: Virtual time in milliseconds since the epoch, used to
                resolve the sticky note's ``${time}`` placeholder.

        Returns:
            The same list instance, with the synthetic entries inserted.
        """
        self.__inject_sticky_note(history, base_timestamp)
        if self.character_repo.get_append_timestamp(self.chat_repo.character):
            for i in range(len(history) - 1, -1, -1):
                if history[i]["role"] == "user":
                    time_str = self.build_timestamp_metadata(base_timestamp=base_timestamp, with_elapsed_time=True)
                    history[i]["content"] = f"{history[i]["content"]}\n\n{time_str}"
                    break
        return history

    def __inject_sticky_note(self, clean_history: list[ChatEntry], base_timestamp: int) -> None:
        """
        Inserts the character's sticky note at its configured position.

        The position is the character's ``sticky_note_pos`` and counts how many
        *user* messages (agent-flagged or not) must follow the note in the
        history. ``0`` (the default) appends the note as the very last entry,
        which the model follows most reliably; ``1`` places it right before the
        last user message; larger values move it further back. When the history
        holds fewer user messages than the configured position, the note is
        inserted at the very front so all available user messages still follow it.

        The note is wrapped in ``<director>`` tags and stored as an agent-flagged
        user entry, mirroring the format the model has always seen. Does nothing
        when the character has no sticky note.

        Any ``${time}`` placeholder in the note is substituted with the in-world
        time derived from ``base_timestamp``, mirroring the ``${time}``
        substitution in the plot generation prompt so a stored plot can reference
        the scene's current time.

        The entry carries the sentinel :data:`INJECTED_STICKY_NOTE_TIMESTAMP` so the
        frontend can recognize the bubble and clear the sticky_note on delete
        instead of trying to delete a stored message. The timestamp is unused by
        the LLM, which only receives the role and content.

        Args:
            clean_history: The already filtered history; mutated in place.
            base_timestamp: Virtual time in milliseconds since the epoch used to
                resolve the ``${time}`` placeholder.
        """
        sticky_note = self.character_repo.get_sticky_note(self.character)
        if not sticky_note:
            return

        # Resolve the ``${time}`` placeholder from the supplied virtual time.
        if "${time}" in sticky_note:
            time_str = self.format_in_world_time(datetime.fromtimestamp(base_timestamp / 1000))
            sticky_note = sticky_note.replace("${time}", time_str)

        pos = self.character_repo.get_sticky_note_pos(self.character)
        if pos <= 0:
            # The note becomes the very last history entry.
            insert_idx = len(clean_history)
        else:
            # Walk backwards counting user messages; insert right before the
            # ``pos``-th user message from the end so exactly ``pos`` user
            # messages follow the note. Default to the front when there are
            # fewer user messages than requested.
            insert_idx = 0
            user_count = 0
            for i in range(len(clean_history) - 1, -1, -1):
                if clean_history[i]["role"] == "user":
                    user_count += 1
                    if user_count == pos:
                        insert_idx = i
                        break

        sticky_note_entry: ChatEntry = {
            "timestamp": INJECTED_STICKY_NOTE_TIMESTAMP,
            "role": "user",
            "content": f"<agent>\n{sticky_note}\n</agent>",
            "is_agent": True,
        }
        clean_history.insert(insert_idx, sticky_note_entry)

    def get_recent_history(self, history: list[ChatEntry], full_history_for_last_n: int = 32) -> list[ChatEntry]:
        if full_history_for_last_n <= 0:
            return []

        # Optimize for KV cache: append up to n/2 messages without changing the previous history.
        cache_window = int(full_history_for_last_n / 2)
        factor = math.exp(math.log(2) / full_history_for_last_n)
        distance = 1.0

        i = len(history) - 1
        compress_from = int(i / cache_window) * cache_window

        recent_history = []
        while i >= 0:
            recent_history.append(history[i])
            i -= int(distance)
            if i < compress_from:
                distance *= factor
        recent_history.reverse()
        return recent_history

    def get_history_text(
        self,
        history: list[ChatEntry],
        full_history_for_last_n: int = 32,
        user_name: str = "USER",
        character_name: str = "ASSISTANT",
    ) -> str:
        """
        Creates a rolling summary by determining the distance to the previous element using an exponential function.
        Newer entries (full_history_for_last_n) are therefore saved in full, while for older ones only every nth element is kept.

        The role of each entry is rendered as an uppercased speaker label derived
        from ``user_name`` and ``character_name`` (instead of the generic USER and
        ASSISTANT), which gives the LLM clearer attribution of who said what.
        """
        # \p{L} = Letters (all languages incl. umlauts)
        # \p{N} = Numbers
        # \p{P} = Punctuation
        # \p{Z} = Whitespace/Separators
        # \p{Sm} = mathematical symbols
        # The ^ at the beginning negates the whole thing: "Find everything that is NOT in these categories"
        clean_regex = regex.compile(r'[^\p{L}\p{N}\p{P}\p{Z}\p{Sm}]+')
        whitespace_regex = regex.compile(r'[\n\t ]+')

        # Base for exponential function, exp(ln(2) / full_history_for_last_n) gives a distance of 1
        # for the first full_history_for_last_n elements.
        # 22bit number to prevent rounding errors in loop
        factor = round(math.exp(math.log(2) / full_history_for_last_n) * 4194304) / 4194304
        distance = 1.0
        i = len(history) - 1

        summary_str = ""
        while i >= 0:
            message = history[i]
            role = f"[{user_name.upper()}]" if message["role"] == "user" else f"[{character_name.upper()}]"
            content = whitespace_regex.sub(' ', message["content"])
            content = clean_regex.sub('', content)
            summary_str = f"{role} {content}\n{summary_str}"
            i -= int(distance)
            distance *= factor

        return summary_str

    def get_history(self, base_timestamp: int, fromTimestamp: int = 0,
                    debug: bool = False) -> list[ChatEntry]:
        """
        Returns the chat history for frontend display.

        In debug mode the raw, unfiltered history is returned; otherwise tool
        messages are filtered out while agent steering messages are kept so the
        UI can render them as collapsed notes. The sticky note is injected at
        its configured position, so the chat already renders the sticky note
        bubble where the model sees it without any client-side assembly.

        Args:
            base_timestamp: Mandatory virtual time in milliseconds since the epoch,
                always forwarded from the frontend, used to resolve the ``${time}``
                placeholder of the injected sticky note so the rendered bubble
                matches what the model sees.
            fromTimestamp: Only include messages newer than this timestamp.
            debug: When True, returns the raw, unfiltered history.
        """
        if debug:
            history = self.get_filtered_chat_history(
                False, False, False, from_timestamp=fromTimestamp,
            )
        else:
            history = self.get_filtered_chat_history(
                from_timestamp=fromTimestamp, filter_agent=False,
            )
        # Display path: no compression, so inject straight onto the filtered history.
        return self.get_injected_chat_history(history, base_timestamp)

    def get_context(self, include_system_prompt: bool = True,
                    base_timestamp: Optional[int] = None) -> str:
        """
        Liefert den Context der aktuellen Chat Session als XML für die Anzeige des Contextes
        im Frontend (für Debugging, Export, etc.) sowie für die Plot Generierung.

        Die Sticky Note wird hier bewusst nicht injiziert: Diese Ansicht dient
        der Inspektion bzw. der Plot-Generierung selbst und soll nicht die
        bestehende Sticky Note enthalten.

        Args:
            base_timestamp: Optional virtual time in milliseconds since the epoch.
                When provided the corresponding in-world date and time is prepended
                to the context so the consumer (e.g. plot generation) knows the
                point in time the context refers to.
        """
        intro = self.character_repo.get_intro(self.character)
        history = self.get_filtered_chat_history(
            clean_user_messages=True, filter_tools=True, filter_agent=True)
        full_history_for_last_n = self.character_repo.get_full_history_for_last_n_plot_generation(
            self.character
        ) or 32

        user_name = self.character_repo.get_user_name(self.character)
        character_name = self.character_repo.get_character_name(self.character)
        history_text = self.get_history_text(
            history,
            full_history_for_last_n=full_history_for_last_n,
            user_name=user_name,
            character_name=character_name,
        )
        context_str = f"# Chat History\n\n{history_text}"
        if include_system_prompt:
            active_system_prompt = self.build_system_prompt()
            context_str += f"\n\n# System Prompt\n\n{active_system_prompt}"
        if intro:
            context_str += f"\n\n# Intro \n\n{intro}"
        if base_timestamp is not None:
            now = datetime.fromtimestamp(base_timestamp / 1000)
            context_str += f"\n\n# Aktueller Zeitpunkt\n\n{self.format_in_world_time(now)}"
        return context_str
