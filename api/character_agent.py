import json
import re
import logging
from typing import Dict
import uuid

from datetime import datetime
from tool_collection import LLMToolCollection
from chat_history import ChatHistory
from llm_result import LLMResult
from llm_service import LLMService

logger = logging.getLogger(__name__)


class CharacterAgent:
    """
    Coordinates LLM inference for a specific character.

    The agent owns everything that requires an inference call (assistant turns,
    proactive messages and plot generation) and the ReAct tool loop.
    All history reading, assembling and non-inferencing mutations are delegated
    to :class:`chat_history.ChatHistory`.
    """

    def __init__(
        self,
        chat_history: ChatHistory,
        llm_service: LLMService,
        tool_coll: LLMToolCollection,
    ) -> None:
        """
        Initializes the agent with the chat history assembler and services.

        Args:
            chat_history: Assembler for context and non-inferencing mutations.
                The character and chat repositories are taken from it.
            llm_service: Service for interacting with the language model.
            tool_coll: Collection of available tools for the agent.
        """
        self.chat_history = chat_history
        self.character_repo = chat_history.character_repo
        self.chat_repo = chat_history.chat_repo
        self.llm_service = llm_service
        self.character = chat_history.character
        self.tool_collection = tool_coll

        self.days = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        self.append_timestamp = self.character_repo.get_append_timestamp(
            self.character
        )

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

        last_user_message_ts = self.chat_repo.get_last_message_timestamp("user", include_virtual_ts=False)
        last_agent_message_ts = max(
            self.chat_repo.get_last_message_timestamp("agent", include_virtual_ts=False),
            self.chat_repo.get_last_message_timestamp("assistant", include_virtual_ts=False))
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
        # Forward the in-world moment as the virtual base timestamp so the sticky
        # note's ``${time}`` placeholder resolves to the same time the agent message reports.
        base_timestamp = int(now.timestamp() * 1000)
        return self.process_agent_message(message, base_timestamp=base_timestamp)

    def process_user_message(self, content: str, base_timestamp: int) -> LLMResult:
        """
        Processes an incoming user message and returns the agent's response.

        Args:
            content: The raw text input from the user.
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; it sets the injected ``<timestamp>``
                metadata and the in-world time of the turn.

        Returns:
            The structured LLM result for the assistant turn, carrying the
            cleaned response text and the total token count of the call.
        """
        logger.info(f"[USER] {content}")
        self.chat_repo.add_user_message(content, virtual_ts=base_timestamp)
        return self.__process_history(base_timestamp=base_timestamp)

    def generate_plot(self, base_timestamp: int) -> None:
        """
        Generates a director plot and stores it as the character's sticky note.

        A dedicated "director" LLM call derives a creative plot instruction from
        the current session context.
        
        Args:
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; its in-world time replaces the
                ``${time}`` placeholder in the plot generation prompt.
        """
        context = self.chat_history.get_context(include_system_prompt=False, include_intro=False, base_timestamp=base_timestamp)
        history: list = [{
            "role": "user",
            "content": context
        }]

        plot_generation_prompt = self.character_repo.get_plot_generation_prompt(self.character)
        # Substitute the ``${time}`` placeholder with the in-world start time.
        base_datetime = datetime.fromtimestamp(base_timestamp / 1000)
        plot_generation_prompt = plot_generation_prompt.replace(
            "${time}", self.chat_history.format_in_world_time(base_datetime)
        )
        history.append({
            "role": "user",
            "content": plot_generation_prompt
        })

        gen_params = { "temperature": 1.2, "min_p": 0.05, "top_p": 1, "top_k": 0, "max_tokens": 32768 }
        llm_result = self.llm_service.send_messages(
            None,
            history,
            tools=None,
            enable_thinking=True,
            reset_cache=True,
            **gen_params
        )
        self.llm_service.reset()
        # Remove reasoning
        plot = re.sub(r"<\|.*\|>", "", llm_result.content, flags=re.DOTALL)
        # Remove XML elements, if LLM answers with <director>
        plot = re.sub(r"<[^>]*>", "", plot, flags=re.DOTALL).strip()
        #self.chat_repo.add_director_message(plot, base_timestamp)
        #self.character_repo.set_sticky_note(self.character, plot)
        self.character_repo.set_intro(self.character, plot)

    def process_agent_message(self, message: str, base_timestamp: int) -> LLMResult:
        """
        Processes an automatic, agent-initiated message.

        This is used for proactive messages, where the agent starts the
        interaction based on internal logic (e.g., time passing). It is invoked
        server-side; the caller supplies the in-world moment as ``base_timestamp``.

        Args:
            message: The system-level message to initiate the response.
            base_timestamp: Virtual time in milliseconds since the epoch, used to
                resolve the ``${time}`` placeholder of the injected sticky note.

        Returns:
            The structured LLM result for the agent-initiated turn.
        """
        logger.info(f"[AGENT] {message}")
        self.chat_repo.add_agent_message(message)
        return self.__process_history(base_timestamp=base_timestamp)

    def request_assistant_message(self, recreate: bool, base_timestamp: int) -> LLMResult:
        """
        Requests an assistant turn based on the current chat history.

        When ``recreate`` is True the most recent assistant message block is
        removed first, so the model regenerates a fresh reply for the exact same
        preceding context. When False the existing history is left intact and an
        additional assistant message is appended on top of it.

        Args:
            recreate: If True, deletes the last assistant message before
                generating a replacement. If False, requests an additional
                assistant turn without removing anything.
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; it resolves the in-world time of the
                turn (injected as ``<timestamp>`` metadata into the agent
                instruction when ``recreate`` is False, and used to resolve the
                sticky note's ``${time}`` placeholder in both cases).

        Returns:
            The structured LLM result for the assistant turn.
        """
        director_message_ts = 0
        if not recreate:
            director_message_ts = self.chat_repo.add_director_message("Advance the plot.", virtual_ts=base_timestamp)
        # else:
        #     self.chat_repo.delete_last_assistant_message()
        result = self.__process_history(base_timestamp=base_timestamp)
        if director_message_ts:
            self.chat_repo.delete_message(director_message_ts)
            self.llm_service.reset()
        return result

    def __process_history(self, base_timestamp: int) -> LLMResult:
        """
        Executes the core ReAct (Reasoning and Acting) loop.

        This method sends the current chat history to the LLM. If the LLM
        requests a tool call, it executes the tool, adds the result to the
        history, and repeats the process until the LLM generates a final
        textual response.

        Args:
            base_timestamp: Virtual time in milliseconds since the epoch, used to
                resolve the ``${time}`` placeholder of the injected sticky note.
            cap_history: When set, only the most recent ``cap_history`` history
                entries are loaded for inference, regardless of role. ``None``
                loads the full history.

        Returns:
            The structured LLM result of the final, non-tool-call inference
            iteration. ``total_tokens`` mirrors the prompt plus completion
            tokens of that last call, which the frontend uses to display
            how full the model context currently is.
        """
        llm_tools = self.tool_collection.generate_tools_array()
        active_system_prompt = self.chat_history.build_system_prompt(include_intro=True)
        gen_params = self.character_repo.get_generation_params(self.character)
        enable_thinking = self.character_repo.get_enable_thinking(self.character)

        full_history_for_last_n = self.character_repo.get_full_history_for_last_n(
            self.character
        ) or 0
        cap_history = self.character_repo.get_cap_history(self.character)

        # Assemble the context in a clean order: filter, then compress, then
        # inject. Injecting the sticky note last keeps it positioned relative to
        # the messages actually sent and prevents the compression from dropping
        # it; ``base_timestamp`` resolves its ``${time}`` placeholder to the
        # in-world time of this turn.
        history = self.chat_history.get_filtered_chat_history(
            clean_user_messages=False, filter_tools=False, filter_agent=False,
            cap_history=cap_history,
            current_scene_only=True,
        )

        if full_history_for_last_n > 0:
            history = self.chat_history.get_recent_history(history=history, full_history_for_last_n=full_history_for_last_n)
        history = self.chat_history.get_injected_chat_history(history, base_timestamp)
        # Whether to flush the KV cache before this turn is a per-character setting.
        reset_cache = self.character_repo.get_reset_cache(self.character)

        llm_result = self.llm_service.send_messages(
            active_system_prompt,
            history,
            llm_tools,
            enable_thinking = enable_thinking,
            reset_cache = reset_cache,
            **gen_params
        )
        logger.info(f"[ASSIST]\n{llm_result.content}")
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

            # Append the assistant tool call and its result directly to the
            # working context instead of re-assembling the whole history. The
            # XML snapshot and the foundational context (intro)
            # assembled before the loop stay untouched, so the ReAct iteration
            # keeps full tool context without duplicating the context assembly.
            history.append({
                "role": "assistant",
                "content": llm_result.content,
                "tool_calls": tool_calls_array,
            })
            history.append({
                "role": "tool",
                "name": tool_call_info["func_name"],
                "content": str(result),
                "tool_call_id": call_id,
            })

            # In-turn continuation: the sequence so far was just computed, so the
            # SWA window is synced to its end and reusing the prefix cache here is
            # correct. Skip the reset to avoid reprocessing the whole prompt for
            # every tool iteration.
            llm_result = self.llm_service.send_messages(
                active_system_prompt,
                history,
                llm_tools,
                enable_thinking=enable_thinking,
                reset_cache=False,
                **gen_params
            )
            tool_call_info = self.llm_service.get_tool_call(llm_result.content)

        self.chat_repo.add_assistant_message(llm_result.content)
        # Remove reasoning
        clean_response = re.sub(r"^.*(<\/think>|\|>)", "", llm_result.content, flags=re.DOTALL).strip()
        # Remove XML elements, if LLM answers with them.
        clean_response = re.sub(r"<[^>]*>[^<]*<[^>]*>", "", clean_response, flags=re.DOTALL).strip()

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
