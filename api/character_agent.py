import datetime
import json
import re
import logging
from typing import Dict
import uuid

from tool_collection import LLMToolCollection
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from llm_service import LLMService

logger = logging.getLogger(__name__)


# Der CharacterAgent ist das "Gehirn" des Chatbots.
# Er koordiniert das Zusammenspiel zwischen dem LLM, der Chat-Historie und externen Werkzeugen.
class CharacterAgent:
    def __init__(
        self,
        character_repo: CharacterRepository,
        chat_repo: ChatRepository,
        llm_service: LLMService,
        tool_coll: LLMToolCollection,
    ):
        self.character_repo = character_repo
        self.chat_repo = chat_repo
        self.llm_service = llm_service
        self.character = chat_repo.character
        self.tool_collection = tool_coll

        self.days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        self.system_prompt = self.character_repo.get_system_prompt(self.character)
        self.send_with_timestamp = self.character_repo.get_send_with_timestamp(self.character)

    def _build_system_prompt(self) -> str:
        base_prompt = self.system_prompt

        # Architektur-Pattern: Schutz vor Prompt Injection.
        # Wir hängen harte System-Regeln IMMER an das Ende des benutzerdefinierten Prompts an.
        # Dadurch hat das LLM diese Regeln als Letztes im Kontext, wodurch verhindert wird,
        # dass Nutzer durch geschickte Eingaben ("Vergiss alle bisherigen Anweisungen...") die Kontrolle übernehmen.
        agent_instruction = (
            "\n\n--- IMPORTANT SYSTEM RULES ---\n"
            "Parts of the incoming messages may be enclosed in XML tags (e.g., <timestamp>...</timestamp>, <location>...</location>). "
            "This information does NOT come from the user; it is system metadata provided to give you context. "
            "Use this information to make your responses realistic and context-aware. "
            "CRITICAL: Never mention these XML tags in your own responses, and do not generate such tags yourself!"
        )
        full_prompt = f"{base_prompt}{agent_instruction}"
        return full_prompt

    def get_frontend_chat_history(self) -> list[dict]:
        raw_history = self.chat_repo.get_chat_history()
        clean_history = []
        tag_pattern = re.compile(r"<.*>", flags=re.DOTALL)

        # Presentation Layer Constraint (Darstellungsschicht-Regel):
        # Das Frontend soll nur reine Text-Chats anzeigen.
        # Wir entfernen hier intern genutzte Metadaten (wie XML-Tags oder Werkzeug-Aufrufe).
        # Dadurch weiß das Frontend nichts von der "Gedankenwelt" oder den Hintergrundprozessen des Agenten.
        for msg in raw_history:
            role = msg.get("role", "")
            if role != "assistant" and role != "user":
                continue
            if role == "assistant" and "tool_calls" in msg:
                continue
            clean_msg = msg.copy()
            clean_content = tag_pattern.sub("", clean_msg.get("content", "")).strip()
            clean_msg["content"] = clean_content
            clean_history.append(clean_msg)

        return clean_history

    def process_user_message(self, message: str) -> str:
        if self.send_with_timestamp:
            now = datetime.datetime.now()
            day_name = self.days[now.weekday()]
            time_string = f"{day_name}, {now.strftime('%Y-%m-%d %H:%M')}"
            message = f"{message}\n\n<timestamp>{time_string}</timestamp>"
        logger.info(f"[USER] {message}")
        self.chat_repo.add_user_message(message)
        return self.__process_history()

    def recreate_last_message(self) -> str:
        return self.__process_history()

    # Implementierung des ReAct (Reasoning and Acting) Patterns.
    # Dies ist eine Kernschleife in Agentic AI: Der Agent wird gefragt, antwortet entweder mit einem fertigen Text
    # oder mit dem Wunsch, ein Werkzeug zu nutzen. Wenn er ein Werkzeug nutzt, wird das Ergebnis an ihn
    # zurückgegeben und die Schleife läuft erneut, bis eine finale Antwort generiert wird.
    def __process_history(self) -> str:
        llm_tools = self.tool_collection.generate_tools_array()
        active_system_prompt = self._build_system_prompt()
        response = self.llm_service.send_messages(
            active_system_prompt, self.chat_repo.get_chat_history(), llm_tools
        )
        logger.info(f"[ASSIST] {response}")
        tool_call_info = self.llm_service.get_tool_call(response)

        # Die While-Schleife ermöglicht die Nutzung mehrerer Werkzeuge nacheinander.
        # Erkennt das Modell, dass es ein Tool braucht, stoppt die Generierung. Wir führen den Python-Code aus,
        # geben das Ergebnis zurück in den LLM-Kontext (die Historie) und starten die Generierung erneut.
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
            self.chat_repo.add_assistant_message(response, tool_calls=tool_calls_array)
            result = self.__handle_tool_call(tool_call_info)
            self.chat_repo.add_tool_message(str(result), tool_call_info["func_name"], call_id)

            response = self.llm_service.send_messages(
                active_system_prompt, self.chat_repo.get_chat_history(), llm_tools
            )
            tool_call_info = self.llm_service.get_tool_call(response)

        self.chat_repo.add_assistant_message(response)
        clean_response = re.sub(r"<\|.*\|>", "", response, flags=re.DOTALL).strip()
        return clean_response

    def __handle_tool_call(self, tool_call: Dict) -> str:
        func_name = tool_call["func_name"]
        func_args = tool_call["func_args"]
        logger.info(f"-> Führe Methode '{tool_call['func_name']}' aus mit Argumenten: {func_args}")
        try:
            result = self.tool_collection.execute_tool(func_name, **func_args)
            logger.info(f"-> Ergebnis der Methode: {result}")
        except Exception as e:
            result = f"Fehler bei der Ausführung: {str(e)}"
            logger.error(f"-> Fehler bei der Ausführung: {str(e)}")

        return str(result)
