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

# Appended to every generated idea instruction. It addresses the model that
# acts the instruction out in the following assistant turns: without it, the
# whole plot tends to be resolved within a single message.
IDEA_PACING_NOTE = "**One action per message.** Do not rush sequences."



class CharacterAgent:
    """
    Coordinates LLM inference for a specific character.

    The agent owns everything that requires an inference call (assistant turns,
    proactive messages, plot generation, idea instructions and history
    summarization) and the ReAct
    tool loop.
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
        # Forward the in-world moment as the virtual base timestamp so the injected
        # timestamp metadata reports the same time as the agent message.
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

    def generate_plot(self) -> None:
        """
        Generates a director plot and stores it in the character's plot field.

        A dedicated "director" LLM call derives a creative plot instruction from
        the current session context. The configured system prompt defines the
        director role; the configured content (ideas, old plot, task etc.) is
        sent as user message after the context (intro). An already stored plot
        is overwritten; the stored plot is appended to the system prompt of the
        following turns.
        """
        intro = self.chat_history.get_context(
            include_system_prompt=False, include_intro=True, include_history=False, include_plot=False)
        system_prompt = self.character_repo.get_plot_generation_system_prompt(self.character)
        content = self.character_repo.get_plot_generation_content(self.character)

        history: list = [{
            "role": "user",
            "content": f"{intro.strip()}\n\n---\n\n{content.strip()}"
        }]
        #gen_params = self.character_repo.get_generation_params(self.character)
        #gen_params = { "temperature": 1.2, "min_p": 0, "top_p": 1, "top_k": 0, "repeat_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0, "max_tokens": 32768 }
        gen_params = { "temperature": 1, "min_p": 0, "top_p": 0.95, "top_k": 64, "repeat_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0, "max_tokens": 32768 }
        llm_result = self.llm_service.send_messages(
            system_prompt.strip(),
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
        self.character_repo.set_plot(self.character, plot)

    def summarize(self, base_timestamp: int) -> str:
        """
        Condenses the current session into a single summary history entry.

        A dedicated LLM call turns the compact session context into a recap that
        carries everything needed to continue the roleplay. The recap is appended
        as an agent message wrapped in ``<summary>`` tags and the entry preceding
        it is flagged as the last scene message, so the following inference calls
        read the history from the summary onwards instead of replaying every
        message. The history itself is never deleted.

        Args:
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; it dates the elapsed-time hints of the
                assembled context and is recorded as the summary's virtual
                timestamp.

        Returns:
            The generated summary text without its surrounding ``<summary>`` tags.
        """
        summarize_prompt = self.character_repo.get_summarize_prompt(self.character)

        chat_context = self.chat_history.get_context(
            include_system_prompt=False, include_intro=False, include_history=True, include_plot=True)

        user_messages: list = [{
            "role": "user",
            "content": chat_context
        }]

        gen_params = { "temperature": 0.2, "min_p": 0, "top_p": 0.95, "top_k": 64, "repeat_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0, "max_tokens": 32768 }
        llm_result = self.llm_service.send_messages(
            summarize_prompt,
            user_messages,
            tools=None,
            enable_thinking=False,
            reset_cache=True,
            **gen_params
        )
        self.llm_service.reset()
        # Remove reasoning
        summary = re.sub(r"^.*(<\/think>|\|>)", "", llm_result.content, flags=re.DOTALL).strip()
        # Remove XML elements, in case the LLM wrapped its answer in <summary> itself.
        summary = re.sub(r"<[^>]*>", "", summary, flags=re.DOTALL).strip()

        # Flagging the current last entry as the scene boundary before appending
        # the summary keeps the summary itself inside the new scene, so inference
        # starts exactly at it while the preceding history stays stored.
        stored_history = self.chat_repo.get_chat_history()
        if stored_history:
            self.chat_repo.set_last_scene_message(stored_history[-1]["timestamp"], True)
        self.chat_repo.add_agent_message(
            f"<summary>\n{summary}\n</summary>", virtual_ts=base_timestamp
        )
        return summary

    def process_agent_message(self, message: str, base_timestamp: int) -> LLMResult:
        """
        Processes an automatic, agent-initiated message.

        This is used for proactive messages, where the agent starts the
        interaction based on internal logic (e.g., time passing). It is invoked
        server-side; the caller supplies the in-world moment as ``base_timestamp``.

        Args:
            message: The system-level message to initiate the response.
            base_timestamp: Virtual time in milliseconds since the epoch, used for
                the injected timestamp metadata.

        Returns:
            The structured LLM result for the agent-initiated turn.
        """
        logger.info(f"[AGENT] {message}")
        self.chat_repo.add_agent_message(message)
        return self.__process_history(base_timestamp=base_timestamp)

    def request_assistant_message(self, base_timestamp: int) -> LLMResult:
        """
        Requests an assistant turn based on the current chat history.

        The existing history is left intact; the model answers on top of it.

        The character's ``answer_count`` setting controls how many answers are
        produced. Every answer runs through a full turn of its own, so tool
        calls and the response logic are executed correctly for each of them and
        each answer sees the preceding ones in the history.

        Args:
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; it sets the injected timestamp
                metadata.

        Returns:
            The structured LLM result of the last generated assistant turn. Its
            ``total_tokens`` therefore reflects the fullest context of the
            request, which is what the frontend displays.
        """
        answer_count = self.character_repo.get_answer_count(self.character)
        result = None
        for _ in range(answer_count):
            result = self.__process_history(base_timestamp=base_timestamp)
        return result

    def generate_idea(self, idea: str, base_timestamp: int) -> str:
        """
        Turns a user idea into a plot instruction and stores it as a director message.

        The context consists of the intro, the plot and the most recent history
        entries. The user message is assembled as context, configured content
        and the user's idea; the configured system prompt defines the director
        role. The instruction is appended 1:1 as a director message; the
        assistant turn that acts it out is requested separately by the caller.

        System prompt and content are configured per character
        (``idea_generation_system_prompt``, ``idea_generation_content``) and fall
        back to :data:`character_repository.DEFAULT_IDEA_GENERATION_SYSTEM_PROMPT`
        and :data:`character_repository.DEFAULT_IDEA_GENERATION_CONTENT`.

        Args:
            idea: The user's idea the instruction should implement.
            base_timestamp: Virtual time in milliseconds since the epoch. Always
                provided by the frontend; recorded as the director message's
                virtual timestamp.

        Returns:
            The generated instruction including the pacing note, as stored.
        """
        if not idea:
            idea = "Stay in the scene and deepen it with creative ideas."
        recent_history = self.chat_history.get_context(
            include_system_prompt=False, include_intro=True,
            include_plot=True, include_history=True, history_length=32)
        system_prompt = self.character_repo.get_idea_generation_system_prompt(self.character)
        content = self.character_repo.get_idea_generation_content(self.character)
        user_messages: list = [{
            "role": "user",
            "content": f"{recent_history.strip()}\n\n---\n\n{content.strip()}\n\n---\n\n{idea.strip()}"
        }]

        gen_params = { "temperature": 1, "min_p": 0, "top_p": 0.95, "top_k": 64, "repeat_penalty": 1, "presence_penalty": 0, "frequency_penalty": 0, "max_tokens": 32768 }
        llm_result = self.llm_service.send_messages(
            system_prompt.strip(),
            user_messages,
            tools=None,
            enable_thinking=False,
            reset_cache=True,
            **gen_params
        )
        self.llm_service.reset()
        # Remove reasoning
        instruction = re.sub(r"^.*(<\/think>|\|>)", "", llm_result.content, flags=re.DOTALL)
        # Remove XML elements, if the LLM wraps the instruction in tags like <director>.
        instruction = re.sub(r"<[^>]*>", "", instruction, flags=re.DOTALL).strip()
        # instruction = f"{instruction}\n\n{IDEA_PACING_NOTE}"
        self.chat_repo.add_director_message(instruction, virtual_ts=base_timestamp)
        return instruction

    def __process_history(self, base_timestamp: int) -> LLMResult:
        """
        Executes the core ReAct (Reasoning and Acting) loop.

        This method sends the current chat history to the LLM. If the LLM
        requests a tool call, it executes the tool, adds the result to the
        history, and repeats the process until the LLM generates a final
        textual response.

        Args:
            base_timestamp: Virtual time in milliseconds since the epoch, used for
                the injected timestamp metadata.
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
        active_system_prompt = self.chat_history.build_system_prompt(include_intro=True, include_plot=True)
        gen_params = self.character_repo.get_generation_params(self.character)
        enable_thinking = self.character_repo.get_enable_thinking(self.character)

        full_history_for_last_n = self.character_repo.get_full_history_for_last_n(
            self.character
        ) or 0
        cap_history = self.character_repo.get_cap_history(self.character)

        # Assemble the context in a clean order: filter, then compress, then
        # inject. Injecting the sticky note last keeps it positioned relative to
        # the messages actually sent and prevents the compression from dropping
        # it; ``base_timestamp`` dates the injected timestamp metadata with the
        # in-world time of this turn.
        history = self.chat_history.get_filtered_chat_history(
            clean_user_messages=False, filter_tools=False, filter_agent=False,
            cap_history=cap_history,
            current_scene_only=True,
        )

        if full_history_for_last_n > 0:
            history = self.chat_history.get_recent_history(history=history, full_history_for_last_n=full_history_for_last_n)
        history = self.chat_history.get_injected_chat_history(history, base_timestamp)

        # The prefix cache is reused across turns: appending to the history keeps
        # the cached prefix valid. Operations that rewrite the history or run
        # side inferences (edit, delete, plot, summary, idea, translation) reset
        # the cache themselves.
        # logger.info(f"[HISTORY]\n{history}")
        # Because reasoning is not stored in the history, the KV cache must be reset when reasoning is enabled.
        llm_result = self.llm_service.send_messages(
            active_system_prompt,
            history,
            llm_tools,
            enable_thinking = enable_thinking,
            reset_cache = True if enable_thinking else False,
            **gen_params
        )
        logger.info(f"[ASSIST]\n{llm_result.content}")
        tool_call_info = self.llm_service.get_tool_call(llm_result.content)

        # "Act" part of the ReAct pattern
        while tool_call_info is not None:
            logger.info(f"[TOOL CALL]\n{tool_call_info}")
            call_id = "call_" + str(uuid.uuid4())[:8]

            # The arguments stay a mapping instead of a JSON string: the chat
            # template already wraps them in braces, so a pre-serialized "{...}"
            # would be rendered with a second, nested pair of braces.
            tool_calls_array = [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": tool_call_info["func_name"],
                        "arguments": tool_call_info["func_args"] or {},
                    },
                }
            ]

            # The call itself is replayed from ``tool_calls_array``; keeping its
            # raw markup in the text content as well would emit the call twice.
            assistant_content = self.llm_service.strip_tool_call(llm_result.content)

            self.chat_repo.add_assistant_message(assistant_content, tool_calls=tool_calls_array)
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
                "content": assistant_content,
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
            # logger.info(f"[HISTORY]\n{history}")
            llm_result = self.llm_service.send_messages(
                active_system_prompt,
                history,
                llm_tools,
                enable_thinking=enable_thinking,
                reset_cache=True if enable_thinking else False,
                **gen_params
            )
            logger.info(f"[ASSIST]\n{llm_result.content}")
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
