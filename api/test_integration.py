import logging
import sys
from config_manager import ConfigManager
from tool_collection import LLMToolCollection
from character_agent import CharacterAgent
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from llm_service import LLMService

# Dieses Skript dient als Headless-Integrationstest.
# Es lädt die gesamte Abhängigkeitskette (Repositories -> Service -> Agent)
# außerhalb des FastAPI-Kontexts, um die LLM-Generierungslogik isoliert zu testen.
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="(%(asctime)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

llm_service = LLMService.from_modelfile(
    r"gemma-4-31B-it.Q4_K_M.gguf",
    n_ctx=32768,
)
config_manager = ConfigManager("testdata")
llm_tool_coll = LLMToolCollection("tools", "testdata", config_manager, llm_service)
llm_tools = llm_tool_coll.generate_tools_array();
logger.info(llm_tools)

character_repo = CharacterRepository("testdata", "test")
character_repo.insert_character("weatherforecaster", "", send_with_timestamp=False)

chat_repo = ChatRepository("testdata", "test", "weatherforecaster")
character_agent = CharacterAgent(character_repo, chat_repo, llm_service, llm_tools)
template = llm_service.get_metadata().get(
    "tokenizer.chat_template", "Kein Template in dieser Datei gefunden!"
)
logger.info(template)

response = character_agent.process_user_message("Ist heute ein Feiertag in Österreich?")
