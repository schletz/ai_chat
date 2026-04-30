import json
import re
import logging
from typing import Dict, Optional
import uuid

from datetime import datetime
from tool_collection import LLMToolCollection
from character_repository import CharacterRepository
from chat_repository import ChatEntry, ChatRepository
from llm_result import LLMResult
from llm_service import LLMService

logger = logging.getLogger(__name__)


class CharacterAgent:
    """
    Coordinates interactions between the LLM, chat history, and external tools
    to generate responses for a specific character.
    """

    def __init__(
        self,
        character_repo: CharacterRepository,
        chat_repo: ChatRepository,
        llm_service: LLMService,
        tool_coll: LLMToolCollection,
    ) -> None:
        """
        Initializes the agent with required repositories and services.

        Args:
            character_repo: Repository for character data and prompts.
            chat_repo: Repository for managing chat history.
            llm_service: Service for interacting with the language model.
            tool_coll: Collection of available tools for the agent.
        """
        self.character_repo = character_repo
        self.chat_repo = chat_repo
        self.llm_service = llm_service
        self.character = chat_repo.character
        self.tool_collection = tool_coll

        self.days = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        self.system_prompt = self.character_repo.get_system_prompt(self.character)
        self.send_with_timestamp = self.character_repo.get_send_with_timestamp(
            self.character
        )

    def _build_system_prompt(self) -> str:
        """
        Constructs the full system prompt by injecting critical system rules.

        These rules instruct the LLM on how to handle system-provided metadata
        (like XML tags) without exposing them to the user.

        Returns:
            The complete system prompt string.
        """
        base_prompt = self.system_prompt

        agent_instruction = (
            "\n\n--- IMPORTANT SYSTEM RULES ---\n"
            "Parts of the incoming messages may be enclosed in XML tags "
            "(e.g., <timestamp>...</timestamp>, <agent>...</agent>). This "
            "information does NOT come from the user; it is system metadata "
            "provided to give you context. Use this information to make your "
            "responses realistic and context-aware. CRITICAL: Never mention "
            "these XML tags in your own responses, and do not generate such "
            "tags yourself!"
        )
        return f"{base_prompt}{agent_instruction}"

    def should_initiate_response(self, current_timestamp: int) -> bool:
        """
        Determines if the agent should proactively initiate a response based on
        a unified idle threshold.

        Args:
            current_timestamp: The current time in milliseconds since the epoch.

        Returns:
            True if the idle thresholds are exceeded, otherwise False.
        """
        idle_threshold_ms = self.character_repo.get_idle_threshold_ms(self.character)
        
        last_user_message_ts = self.chat_repo.get_last_message_timestamp("user")
        last_agent_message_ts = max(
            self.chat_repo.get_last_message_timestamp("agent"),
            self.chat_repo.get_last_message_timestamp("assistant"))
        if not last_user_message_ts and not last_agent_message_ts:
            return False
        if last_agent_message_ts > current_timestamp - idle_threshold_ms:
            return False
        if last_user_message_ts > current_timestamp - idle_threshold_ms:
            return False
        return True

    def initiate_response(self, now: datetime) -> LLMResult:
        """
        Generates a proactive agent message based on the current time.

        This method creates a special system-level message to prompt the LLM
        into generating a context-aware continuation of the conversation.

        Args:
            now: The current datetime object.

        Returns:
            The LLM result for the agent-initiated response, including the
            cleaned text and the total token count of the inference call.
        """
        day_name = self.days[now.weekday()]
        time_string = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"
        message = (
            f"<agent>It's now {time_string}. The user has not responded for "
            "some time. In the meantime, everything has gone according to plan. "
            "If it does not make sense to send a message (for example, if the "
            "user is sleeping), generate an absolute EMPTY message that I can "
            "check with an if statement. Otherwise, briefly describe what has "
            "happened in the meantime and continue."
            "</agent>"
        )
        return self.process_agent_message(message)

    def get_filtered_chat_history(
        self, 
        clean_user_messages: bool = True,
        filter_tools: bool = True, 
        filter_agent: bool = True,
        from_timestamp: int = 0
    ) -> list[ChatEntry]:
        """
        Filters and cleans the chat history for frontend display or LLM inference.

        Args:
            clean_user_messages: If True, removes XML tags from user messages.
            filter_tools: If True, removes tool call and tool response messages.
            filter_agent: If True, removes agent-initiated system messages.
            from_timestamp: Only include messages with a timestamp strictly greater than this value.

        Returns:
            A list of cleaned message dictionaries suitable for UI rendering or inference.
        """
        raw_history = self.chat_repo.get_chat_history()
        clean_history = []
        # This regex pattern finds and removes XML-like tags and their content.
        tag_pattern = re.compile(r"<[^>]+>.*<[^>]+>", flags=re.DOTALL)
        # More aggresive pattern for assistant messages.
        # Qwen sends closing XML tags without opening tags.
        assistant_tag_pattern = re.compile(r"^.*<[^>]+>", flags=re.DOTALL)

        for msg in raw_history:
            if msg.get("timestamp", 0) <= from_timestamp:
                continue

            role = msg["role"]
            if filter_tools and role == "assistant" and "tool_calls" in msg:
                continue
            if filter_tools and role == "tool":
                continue
            if filter_agent and msg.get("is_agent", False) is True:
                continue

            raw_content = msg["content"]
            if role == "user" and not clean_user_messages:
                raw_content = f"{raw_content}\n\n{msg.get('additional_content', '')}"

            if role == "assistant":
                clean_content = assistant_tag_pattern.sub("", raw_content).strip() if "tool_calls" not in msg else raw_content
            elif role == "user":
                clean_content = tag_pattern.sub("", raw_content).strip() if clean_user_messages else raw_content
            else:
                clean_content = raw_content
                
            if len(clean_content) > 0:
                clean_msg = msg.copy()
                clean_msg["content"] = clean_content
                clean_history.append(clean_msg)

        return clean_history

    def create_summary(self, n: int = 5) -> Optional[LLMResult]:
        """
        Generates a summary of the chat history while keeping the last n messages
        active (unsummarized) to maintain immediate conversation context.

        When a previous summary exists, only messages newer than its timestamp
        are fed into the new summarization, preventing the prompt from growing
        unboundedly on long chats. The previous summary is provided to the LLM
        as foundational context so the new summary can extend rather than
        replace it. The character intro is intentionally NOT included.

        Args:
            n: Number of most recent messages to keep outside the summary.

        Returns:
            The structured LLM result of the summarization call, or ``None``
            when no summarization happened because the history is still short
            enough to fit.
        """
        previous_summary = self.character_repo.get_summary(self.character)
        from_ts = previous_summary["timestamp"] if previous_summary else 0

        # We fetch the history including tool results to provide the LLM with full context for the summary.
        full_history = self.get_filtered_chat_history(
            clean_user_messages=False, filter_tools=False, filter_agent=False,
            from_timestamp=from_ts
        )

        if len(full_history) <= n:
            logger.info("Not enough messages to justify a summary while keeping n active.")
            return None

        # Rolling window logic: Split history into 'to be summarized' and 'to remain active'.
        # The stored timestamp will be the timestamp of the last message included in the summary.
        split_index = len(full_history) - n
        summary_input_slice = full_history[:split_index]
        last_summarized_msg = summary_input_slice[-1]
        last_msg_timestamp = last_summarized_msg["timestamp"]

        system_prompt = (
            "You are an analytical AI assistant. Your task is to summarize the provided roleplay chat history."
        )

        messages: list = []
        if previous_summary:
            # Seed the model with the prior summary so it can extend it rather
            # than re-summarize content it has never seen.
            messages.append({
                "role": "user",
                "content": (
                    "<previous_summary>\n"
                    f"{previous_summary['text']}\n"
                    "</previous_summary>"
                )
            })
        messages.extend(summary_input_slice)

        if previous_summary:
            instruction = (
                "A previous summary of the earlier chat history is provided above inside "
                "<previous_summary> tags, followed by the messages that have occurred since. "
                "Produce a single, updated summary that integrates the previous summary with "
                "the new messages. Focus on the essential details, character relationships, "
                "and key events that are strictly relevant for continuing the roleplay. "
                "Output ONLY the summary text."
            )
        else:
            instruction = (
                "Summarize the chat history up to this point. Focus on the essential details, "
                "character relationships, and key events that are strictly relevant for continuing the roleplay. "
                "Output ONLY the summary text."
            )

        messages.append({
            "role": "user",
            "content": instruction,
        })

        gen_params = { "temperature": 0.1 }

        summary_result = self.llm_service.send_messages(
            system_prompt,
            messages,
            tools=[],
            **gen_params
        )
        clean_summary = re.sub(r"<\|.*\|>", "", summary_result.content, flags=re.DOTALL).strip()
        self.character_repo.set_summary(self.character, clean_summary, last_msg_timestamp)
        logger.info(f"Generated new summary for '{self.character}' covering context up to timestamp {last_msg_timestamp}.")
        # Reset KV cache
        self.llm_service.reset()
        return LLMResult(content=clean_summary, total_tokens=summary_result.total_tokens)

    def process_user_message(self, content: str, base_timestamp: Optional[int] = None) -> LLMResult:
        """
        Processes an incoming user message and returns the agent's response.

        Args:
            content: The raw text input from the user.
            base_timestamp: Optional virtual time in milliseconds since the epoch.
                When provided it overrides the current system clock for the
                injected ``<timestamp>`` metadata. If ``None`` the system time
                is used instead.

        Returns:
            The structured LLM result for the assistant turn, carrying the
            cleaned response text and the total token count of the call.
        """
        additional_content = ""
        if self.send_with_timestamp:
            now = datetime.fromtimestamp(base_timestamp / 1000) if base_timestamp is not None else datetime.now()
            day_name = self.days[now.weekday()]
            time_string = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"
            additional_content = f"<timestamp>{time_string}</timestamp>"

        logger.info(f"[USER] {content} {additional_content}")
        self.chat_repo.add_user_message(content, additional_content, virtual_ts=base_timestamp)
        return self.__process_history()

    def process_agent_message(self, message: str) -> LLMResult:
        """
        Processes an automatic, agent-initiated message.

        This is used for proactive messages, where the agent starts the
        interaction based on internal logic (e.g., time passing).

        Args:
            message: The system-level message to initiate the response.

        Returns:
            The structured LLM result for the agent-initiated turn.
        """
        logger.info(f"[AGENT] {message}")
        self.chat_repo.add_agent_message(message)
        return self.__process_history()

    def recreate_last_message(self) -> LLMResult:
        """
        Regenerates the last assistant message based on the current history.

        Returns:
            The structured LLM result for the regenerated assistant turn.
        """
        self.chat_repo.delete_last_assistant_message()
        # Clear KV cache.
        self.llm_service.reset()
        return self.__process_history()

    def __process_history(self) -> LLMResult:
        """
        Executes the core ReAct (Reasoning and Acting) loop.

        This method sends the current chat history to the LLM. If the LLM
        requests a tool call, it executes the tool, adds the result to the
        history, and repeats the process until the LLM generates a final
        textual response.

        Returns:
            The structured LLM result of the final, non-tool-call inference
            iteration. ``total_tokens`` mirrors the prompt plus completion
            tokens of that last call, which the frontend uses to display
            how full the model context currently is.
        """
        llm_tools = self.tool_collection.generate_tools_array()
        active_system_prompt = self._build_system_prompt()
        gen_params = self.character_repo.get_generation_params(self.character)

        # Context Window Management: Inject summary if available
        summary = self.character_repo.get_summary(self.character)
        intro = self.character_repo.get_intro(self.character)
        plot = self.character_repo.get_plot(self.character)
        from_ts = summary["timestamp"] if summary else 0

        chat_history = self.get_filtered_chat_history(
            clean_user_messages=False, filter_tools=False, filter_agent=False, from_timestamp=from_ts
        )

        # Foundational context is prepended in narrative order: intro first
        # (the framing of the roleplay), then summary (what has happened so far),
        # then plot (the intended storyline for the current day).
        if plot:
            chat_history.insert(0, {
                "role": "user",
                "content": f"<plot>\n{plot}\n</plot>"
            })
        if summary:
            chat_history.insert(0, {
                "role": "user",
                "content": f"<summary>\n{summary['text']}\n</summary>"
            })
        if intro:
            chat_history.insert(0, {
                "role": "user",
                "content": f"<intro>\n{intro}\n</intro>"
            })

        llm_result = self.llm_service.send_messages(
            active_system_prompt,
            chat_history,
            llm_tools,
            **gen_params
        )
        logger.info(f"[ASSIST] {llm_result.content}")
        tool_call_info = self.llm_service.get_tool_call(llm_result.content)

        # "Act" part of the ReAct pattern
        while tool_call_info is not None:
            logger.info(f"[TOOL CALL] {tool_call_info}")
            call_id = "call_" + str(uuid.uuid4())[:8]

            tool_calls_array = [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call_info["func_name"],
                        "arguments": json.dumps(tool_call_info["func_args"]),
                    },
                }
            ]

            self.chat_repo.add_assistant_message(llm_result.content, tool_calls=tool_calls_array)
            result = self.__handle_tool_call(tool_call_info)
            self.chat_repo.add_tool_message(
                str(result), tool_call_info["func_name"], call_id
            )

            # Re-fetch history to include the newly executed tool result
            chat_history = self.get_filtered_chat_history(
                clean_user_messages=False, filter_tools=False, filter_agent=False, from_timestamp=from_ts
            )

            if plot:
                chat_history.insert(0, {
                    "role": "user",
                    "content": f"<plot>\n{plot}\n</plot>"
                })
            if summary:
                chat_history.insert(0, {
                    "role": "user",
                    "content": f"<summary>\n{summary['text']}\n</summary>"
                })
            if intro:
                chat_history.insert(0, {
                    "role": "user",
                    "content": f"<intro>\n{intro}\n</intro>"
                })

            llm_result = self.llm_service.send_messages(
                active_system_prompt,
                chat_history,
                llm_tools,
                **gen_params
            )
            tool_call_info = self.llm_service.get_tool_call(llm_result.content)

        self.chat_repo.add_assistant_message(llm_result.content)
        clean_response = re.sub(r"<\|.*\|>", "", llm_result.content, flags=re.DOTALL).strip()

        # Automatic context compaction: once the most recent inference call has
        # consumed more tokens than the configured threshold, fold the older
        # portion of the conversation into a rolling summary so subsequent turns
        # stay inside the model's context window.
        auto_summarize_tokens = self.character_repo.get_auto_summarize_tokens(self.character)
        if auto_summarize_tokens is not None and llm_result.total_tokens > auto_summarize_tokens:
            logger.info(
                f"Auto-summarize triggered for '{self.character}': "
                f"{llm_result.total_tokens} > {auto_summarize_tokens}."
            )
            self.create_summary()

        return LLMResult(content=clean_response, total_tokens=llm_result.total_tokens)

    def __handle_tool_call(self, tool_call: Dict) -> str:
        """
        Executes a requested tool and returns its result as a string.

        Args:
            tool_call: A dictionary containing the function name and arguments.

        Returns:
            The string representation of the tool's execution result.
        """
        func_name = tool_call["func_name"]
        func_args = tool_call["func_args"]
        logger.info(
            f"-> Executing method '{func_name}' with arguments: {func_args}"
        )

        try:
            result = self.tool_collection.execute_tool(func_name, **func_args)
            logger.info(f"-> Method result: {result}")
        except Exception as e:
            result = f"Error during execution: {str(e)}"
            logger.error(f"-> Error during execution: {str(e)}")

        return str(result)