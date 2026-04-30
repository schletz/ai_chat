import os
import logging
import sys

from character_repository import CharacterRepository
from config_manager import ConfigManager
from tool_collection import LLMToolCollection
from chat_history import ChatHistory
from chat_repository import ChatRepository
from character_agent import CharacterAgent
from llm_service import LLMService
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="(%(asctime)s) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("DATA_DIR", "data")
TOOLS_DIR = os.getenv("TOOLS_DIR", "tools")
logger.info(f"Using DATA_DIR: {DATA_DIR}")
logger.info(f"Using TOOLS_DIR: {TOOLS_DIR}")

config_manager = ConfigManager(DATA_DIR)

logger.info(f"Loading model f:\\ai_chat_data\\gemma-4-31B-it-Q6_K.gguf into VRAM...")
llm_service = LLMService("f:\\ai_chat_data\\gemma-4-31B-it-Q6_K.gguf", 32768, -1, True)
logger.info(f"Done. Sending test message to LLM...")
character_repo = CharacterRepository(DATA_DIR, "michael")
chat_repo = ChatRepository(DATA_DIR, "michael", "Plot Generator")
chat_repo.delete_all_messages()
chat_history = ChatHistory(character_repo, chat_repo)
llm_tool_collection = LLMToolCollection(TOOLS_DIR, DATA_DIR, config_manager, llm_service)
tools_array = llm_tool_collection.generate_tools_array()
if len(tools_array) == 0:
    logger.warning("No tools were loaded. Ensure that the tools directory contains valid tool modules.")
    exit(1)
logger.info(f"Loaded {len(tools_array)} tools: {tools_array}")

character_agent = CharacterAgent(chat_history, llm_service, llm_tool_collection)
response = character_agent.process_user_message("Dies ist ein Systemtest. Generiere mit dem Tool eine zufällige Zahl und gib sie aus. Wenn du keine Daten vom Tool bekommen hast, gib einen Fehler aus.", 0)

logger.info(f"[RESPONSE]\n{response.content}")
