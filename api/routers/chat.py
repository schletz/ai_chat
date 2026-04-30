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
    """Retrieve existing chat history. Supports incremental loading via timestamp to reduce bandwidth usage.

    @param name: The character identifier.
    @param fromTimestamp: Unix timestamp for filtering messages. Defaults to 0 (all messages).
    @param char_repo: Injected repository for character data access.
    @param agent: Injected character processing agent.
    @return: List of chat message dictionaries matching the filter criteria.
    """
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
    """Process a user message and generate an AI response.

    @param name: The character identifier.
    @param chat_msg: Parsed request payload containing the user's input.
    @param char_repo: Injected repository for character data access.
    @param agent: Injected character processing agent.
    @param llm_lock: Concurrency lock to serialize LLM inference calls.
    @return: Dictionary containing the assistant role and generated content.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found")

    # Offload blocking LLM inference to a thread pool to prevent event loop starvation.
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
    """Remove the most recent AI response and regenerate it using current context.

    @param name: The character identifier.
    @param char_repo: Injected repository for character data access.
    @param chat_repo: Injected repository for chat history management.
    @param agent: Injected character processing agent.
    @param llm_lock: Concurrency lock to serialize LLM inference calls.
    @return: Dictionary containing the assistant role and regenerated content.
    """
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
    """Permanently remove a specific message from the chat history by its timestamp.

    @param name: The character identifier.
    @param timestamp: Unix timestamp identifying the target message.
    @param chat_repo: Injected repository for chat history management.
    @return: Confirmation dictionary on success.
    @raises HTTPException: 404 if the specified message does not exist in the history.
    """
    if chat_repo.delete_message(timestamp):
        return {"message": "Message deleted."}
    raise HTTPException(status_code=404, detail="Message not found.")