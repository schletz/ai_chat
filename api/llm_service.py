import logging
import re
import yaml
from typing import Dict, List, Optional
from llama_cpp import GGML_TYPE_Q8_0, ChatCompletionRequestMessage, ChatCompletionTool, Llama

from chat_exception import ChatException
from chat_repository import ChatEntry
from llm_result import LLMResult

logger = logging.getLogger(__name__)


class LLMService:
    """Abstracts the complexity of the underlying C++ LLaMA library.

    Provides a clean interface to inject context, manage inference configurations,
    and process special model outputs such as tool calls.
    """

    def __init__(
        self,
        model_path: str,
        n_ctx: int = 16384,
        n_gpu_layers: int = -1,
        enable_thinking: bool = True,
    ) -> None:
        """Load a model and patch its chat handler with the reasoning toggle.

        n_gpu_layers: -1 offloads all layers to GPU (only safe if the full model fits).
        For a 70B model on 32 GB VRAM, set this to a partial count (e.g. ~50 for Q4_K_M).
        enable_thinking: initial reasoning state. Can be toggled later at runtime.
        """
        self._llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            n_batch=1024,
            last_n_tokens_size=512,
            flash_attn=True,
            swa_full=False,
            verbose=False,
            type_k=GGML_TYPE_Q8_0,
            type_v=GGML_TYPE_Q8_0,
        )

        # Capture the model's original (unwrapped) chat handler exactly once.
        # Toggling reasoning re-wraps this base handler, so repeated toggles never
        # stack wrappers on top of each other.
        self._base_chat_handler = (
            self._llm.chat_handler
            or self._llm._chat_handlers.get(str(self._llm.chat_format)) # pylint: disable=protected-access
            or llama_chat_format.get_chat_completion_handler(self._llm.chat_format) # pylint: disable=undefined-variable # type: ignore
        )

        # Detect sliding-window attention (SWA). With ``swa_full=False`` the SWA
        # layers only keep a partial KV ring buffer, so reusing the prefix cache
        # *across turns* (when the sequence changes in the middle) reads stale
        # window entries and the model loses coherence. For SWA models we
        # therefore force a full recompute at the start of every turn instead of
        # relying on the (here incorrect) cross-turn prefix reuse. Full-attention
        # models keep the fast reuse path.
        self._is_swa = any(
            key.endswith("attention.sliding_window") for key in self._llm.metadata
        )
        logger.info(
            "Model loaded (n_ctx=%d, sliding_window_attention=%s).",
            n_ctx, self._is_swa,
        )

        self.enable_thinking(enable_thinking)

    def enable_thinking(self, enable_thinking: bool) -> None:
        """Toggle the model's reasoning output at runtime.

        Re-wraps the original chat handler so the change takes effect on the next
        inference call, without reloading the model. Applies to all models.
        """
        base_chat_handler = self._base_chat_handler

        def chat_handler_with_thinking(*args, **kwargs):
            return base_chat_handler(*args, **{"enable_thinking": enable_thinking, **kwargs})

        self._llm.chat_handler = chat_handler_with_thinking

    def get_metadata(self) -> Dict:
        """Return the metadata dictionary from the underlying LLM instance."""
        return self._llm.metadata

    def reset(self) -> None:
        """Reset the model state, clear KV cache."""
        self._llm.reset()
        logger.info(f"KV cache resetted")
        
    def send_messages(
        self,
        system_prompt: str | None,
        chat_messages: List[ChatEntry],
        tools: Optional[List[ChatCompletionTool]] = None,
        enable_thinking: bool = True,
        reset_cache: bool = True,
        **kwargs
    ) -> LLMResult:
        """Send a sequence of messages and return the stripped model response
        together with the usage statistics reported by the underlying runtime.

        ``enable_thinking`` re-wraps the chat handler before inference so the
        caller controls the model's reasoning output per call, without any
        persistent system-wide state.

        ``reset_cache`` clears the KV cache before inference on sliding-window
        models so the prompt is fully recomputed instead of reusing the (for SWA
        incorrect) cross-turn prefix cache. The first inference of a turn should
        pass ``True``; subsequent in-turn calls (e.g. the ReAct tool loop) may
        pass ``False`` to safely reuse the freshly computed sequence. On
        full-attention models the flag has no effect, keeping fast reuse.
        """
        if tools is None:
            tools = []

        # Apply the requested reasoning state for this inference call.
        self.enable_thinking(enable_thinking)

        # On SWA models the cross-turn prefix cache is invalid (partial window
        # buffer); drop it so the sequence is recomputed cleanly.
        if reset_cache and self._is_swa:
            self._llm.reset()
            logger.info(f"KV cache resetted")

        messages = []
        if system_prompt is not None:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(
            [{"role": message["role"], "content": message["content"]} for message in chat_messages]  # type: ignore
        )

        # Fallback temperature and max_tokens
        if "temperature" not in kwargs:
            kwargs["temperature"] = 0.1
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = 4096

        logger.info(f"[INFO] Inferencing. History length: {len(messages)}")
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
