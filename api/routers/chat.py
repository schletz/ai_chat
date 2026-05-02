from fastapi import APIRouter, Depends, HTTPException, status
import asyncio
from dependencies import get_character_agent, get_chat_repository, get_character_repository, get_llm_lock
from character_agent import CharacterAgent
from chat_repository import ChatRepository
from character_repository import CharacterRepository
from schemas import ChatMessage

router = APIRouter(prefix="/characters")

@router.get("/{name}/chat")
async def get_chat(
    name: str,
    fromTimestamp: int = 0,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent)
):
    """Holt den bisherigen Chat-Verlauf ab. Optional mit Zeitstempel, um nur neue Nachrichten zu laden (Inkrementelles Laden spart Bandbreite)."""
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    history = agent.get_frontend_chat_history()
    if fromTimestamp > 0:
        history = [msg for msg in history if msg.get("timestamp", 0) >= fromTimestamp]
    return history


@router.post("/{name}/chat", status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    name: str,
    chat_msg: ChatMessage,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """Sendet eine Benutzernachricht an den Charakter und generiert eine Antwort."""
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found")

    # WICHTIG: Die Ausführung des LLMs (Inference) ist ressourcenintensiv und blockierend.
    # `asyncio.to_thread` lagert diese Ausführung in einen Hintergrund-Thread aus,
    # damit der Haupt-Event-Loop von FastAPI nicht blockiert wird und weiterhin andere Anfragen bedienen kann.
    async with llm_lock:
        bot_response_text = await asyncio.to_thread(agent.process_user_message, chat_msg.message)

    return {"role": "assistant", "content": bot_response_text}


@router.post("/{name}/chat/recreate", status_code=status.HTTP_201_CREATED)
async def recreate_chat_message(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """Löscht die letzte KI-Antwort und erstellt sie auf Basis der bestehenden Chathistorie neu."""
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo.delete_last_assistant_message()

    async with llm_lock:
        bot_response_text = await asyncio.to_thread(agent.recreate_last_message)

    return {"role": "assistant", "content": bot_response_text}


@router.delete("/{name}/chat/{timestamp}")
async def delete_chat_message(
    name: str,
    timestamp: int,
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """Löscht eine spezifische Nachricht anhand ihres Zeitstempels aus dem Verlauf."""
    if chat_repo.delete_message(timestamp):
        return {"message": "Message deleted."}
    raise HTTPException(status_code=404, detail="Message not found.")
