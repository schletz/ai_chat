import re
import yaml
from typing import Dict, List, Optional
from llama_cpp import ChatCompletionRequestMessage, ChatCompletionTool, Llama

from chat_exception import ChatException
from chat_repository import ChatEntry
from llm_result import LLMResult


class LLMService:
    """Abstracts the complexity of the underlying C++ LLaMA library.

    Provides a clean interface to inject context, manage inference configurations,
    and process special model outputs such as tool calls.
    """

    def __init__(self, llm_instance: Llama) -> None:
        self._llm = llm_instance

    @classmethod
    def from_modelfile(cls, model_path: str, n_ctx: int = 16384, n_gpu_layers: int = -1) -> "LLMService":
        """Initialize the service by loading a model and patching the chat handler.

        n_gpu_layers: -1 offloads all layers to GPU (only safe if the full model fits).
        For a 70B model on 32 GB VRAM, set this to a partial count (e.g. ~50 for Q4_K_M).
        """
        llm_instance = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            n_batch=1024,
            flash_attn=True,
            swa_full=False,
            verbose=False,
        )

        # Retrieve the base chat handler to wrap it with custom logic.
        base_chat_handler = (
            llm_instance.chat_handler
            or llm_instance._chat_handlers.get(str(llm_instance.chat_format)) # pylint: disable=protected-access
            or llama_chat_format.get_chat_completion_handler(llm_instance.chat_format) # pylint: disable=undefined-variable # type: ignore
        )

        def chat_handler_with_thinking(*args, **kwargs):
            return base_chat_handler(*args, **{"enable_thinking": True, **kwargs})

        llm_instance.chat_handler = chat_handler_with_thinking
        return cls(llm_instance=llm_instance)

    def get_metadata(self) -> Dict:
        """Return the metadata dictionary from the underlying LLM instance."""
        return self._llm.metadata

    def reset(self) -> None:
        """Reset the model state, clear KV cache."""
        self._llm.reset()
        
    def send_messages(
        self,
        system_prompt: str,
        chat_messages: List[ChatEntry],
        tools: Optional[List[ChatCompletionTool]] = None,
        **kwargs
    ) -> LLMResult:
        """Send a sequence of messages and return the stripped model response
        together with the usage statistics reported by the underlying runtime.
        """
        if tools is None:
            tools = []

        messages: List[ChatCompletionRequestMessage] = [
            {"role": "system", "content": system_prompt}
        ]
        messages.extend(
            [{"role": message["role"], "content": message["content"]} for message in chat_messages]  # type: ignore
        )

        # Fallback temperature and max_tokens
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0.1
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = 4096

        response = self._llm.create_chat_completion(
            messages=messages,
            tools=tools,
            tool_choice="auto",
            **kwargs
        )
        if not isinstance(response, dict):
            raise ChatException("Invalid return type of chat message.")

        content = str(response["choices"][0]["message"]["content"]).strip()
        usage = response.get("usage") or {}
        total_tokens = int(usage.get("total_tokens", 0))
        return LLMResult(content=content, total_tokens=total_tokens)

    def send_command(
        self,
        system_prompt: str,
        user_prompt: str | List[str],
        tools: Optional[List[ChatCompletionTool]] = None,
        reset: bool = True,
    ) -> str:
        """Execute a command with timing metrics and return the stripped response."""
        if tools is None:
            tools = []

        messages: List[ChatCompletionRequestMessage] = [{"role": "system", "content": system_prompt}]
        if isinstance(user_prompt, str):
            messages.append({"role": "user", "content": user_prompt})
        else:
            for prompt in user_prompt:
                messages.append({"role": "user", "content": prompt})

        if reset:
            self._llm.reset()

        response = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=None,
            temperature=0.1,
            tools=tools,
            tool_choice="auto",
        )
        if not isinstance(response, dict):
            raise ChatException("Invalid return type of chat message.")

        # Check if the generation was truncated due to context limits.
        # hasLengethExeeded = response["choices"][0]["finish_reason"] == "length"
        return str(response["choices"][0]["message"]["content"]).strip()

    def get_tool_call(self, content: str) -> Dict | None:
        """Parse raw model output to extract structured tool call arguments."""
        # Extract function name and JSON-like argument string using regex.
        tool_match = re.search(r"<\|tool_call>call:([^{]+)(\{.*?\})<tool_call\|>", content)
        if not tool_match:
            return None

        func_name = tool_match.group(1)
        func_args_str = tool_match.group(2)

        # Normalize YAML formatting for safe parsing.
        func_args_str = func_args_str.replace(":", ": ", 1)
        func_args_str = func_args_str.replace('<|"|>', '"')

        func_args = yaml.safe_load(func_args_str)
        return {"func_name": func_name, "func_args": func_args}
