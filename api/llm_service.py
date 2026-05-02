import re
import time
import yaml
from typing import Dict, List, Optional
from llama_cpp import ChatCompletionTool, Llama


# Abstrahiert die Komplexität der zugrundeliegenden C++ LLaMA Bibliothek.
# Stellt eine saubere Schnittstelle bereit, um Kontext zu injizieren,
# Inferenz-Konfigurationen zu verwalten und spezielle Modellausgaben (wie Tool-Aufrufe) zu verarbeiten.
class LLMService:
    def __init__(self, llm_instance: Llama):
        self._llm = llm_instance

    @classmethod
    def from_modelfile(cls, model_path: str, n_ctx: int = 16384) -> "LLMService":
        llm_instance = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=n_ctx,
            n_batch=1024,
            flash_attn=True,
            swa_full=False,
            verbose=False,
        )

        base_chat_handler = (
            llm_instance.chat_handler
            or llm_instance._chat_handlers.get(llm_instance.chat_format)
            or llama_chat_format.get_chat_completion_handler(llm_instance.chat_format)
        )

        def chat_handler_with_thinking(*args, **kwargs):
            return base_chat_handler(*args, **{"enable_thinking": True, **kwargs})

        llm_instance.chat_handler = chat_handler_with_thinking

        return cls(llm_instance=llm_instance)

    def get_metadata(self) -> Dict:
        return self._llm.metadata

    def send_messages(
        self,
        system_prompt: str,
        chat_messages: List[Dict[str, str]],
        tools: Optional[List[ChatCompletionTool]] = None,
    ) -> str:
        if tools is None:
            tools = []
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_messages)

        response = self._llm.create_chat_completion(
            messages=messages, max_tokens=None, temperature=0.1, tools=tools, tool_choice="auto"
        )
        return response["choices"][0]["message"]["content"].strip()

    def send_command(
        self,
        system_prompt: str,
        user_prompt: str | List[str],
        tools: Optional[List[ChatCompletionTool]] = None,
        reset: bool = True,
    ) -> Dict:
        if tools is None:
            tools = []
        messages = [{"role": "system", "content": system_prompt}]
        if isinstance(user_prompt, str):
            messages.append({"role": "user", "content": user_prompt})
        else:
            for prompt in user_prompt:
                messages.append({"role": "user", "content": prompt})

        if reset:
            self._llm.reset()
        start = time.time()
        response = self._llm.create_chat_completion(
            messages=messages, max_tokens=None, temperature=0.1, tools=tools, tool_choice="auto"
        )
        end = time.time()
        hasLengethExeeded = True if response["choices"][0]["finish_reason"] == "length" else False
        usage = response["usage"]
        prompt_t = usage["prompt_tokens"]
        completion_t = usage["completion_tokens"]
        total_t = usage["total_tokens"]

        duration = end - start

        tps = completion_t / duration if duration > 0 else 0
        print(f"⏱️ Zeit: {duration:.2f}s")
        print(f"📊 Tokens: {prompt_t} (Prompt) + {completion_t} (Antwort) = {total_t} (Gesamt)")
        print(f"🚀 Speed: {tps:.2f} Tokens/Sekunde (End-to-End)")
        print(f"Length limit exeeded? {hasLengethExeeded}")

        return response["choices"][0]["message"]["content"].strip()

    def get_tool_call(self, content: str) -> Dict | None:
        # Ein Regex (Regulärer Ausdruck) basierter Parser.
        # Er durchsucht den rohen Text-Output des LLM nach speziellen Werkzeug-Aufruf-Mustern.
        # So wird aus unstrukturiertem Text eine strukturierte JSON-Extraktion für den Python-Code.
        tool_match = re.search(r"<\|tool_call>call:([^{]+)(\{.*?\})<tool_call\|>", content)
        if not tool_match:
            return None

        func_name = tool_match.group(1)
        func_args_str = tool_match.group(2)
        # key:val --> key: val or key:<|"|>val<|"|> -> key: "val"
        func_args_str = func_args_str.replace(':', ': ', 1)
        func_args_str = func_args_str.replace('<|"|>', '"')

        func_args = yaml.safe_load(func_args_str)
        return {"func_name": func_name, "func_args": func_args}
