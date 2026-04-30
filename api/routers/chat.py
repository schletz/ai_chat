from fastapi import APIRouter, Depends, HTTPException, status
import asyncio
from dependencies import get_character_agent, get_chat_repository, get_character_repository, get_llm_lock
from character_agent import CharacterAgent
from chat_repository import ChatRepository
from character_repository import CharacterRepository
from schemas import ChatMessage, ChatMessageUpdate

router = APIRouter(prefix="/characters")


@router.get("/{name}/chat")
async def get_chat(
    name: str,
    fromTimestamp: int = 0,
    debug: bool = False,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent)
):
    """
    Retrieves the chat history for a specific character.

    Supports incremental loading by providing a timestamp, which filters for messages
    sent at or after that time.

    Args:
        name: The unique identifier for the character.
        fromTimestamp: A Unix timestamp. If provided, only messages from this
            time onwards are returned. Defaults to 0 (all messages).
        debug: If True, returns unfiltered, raw chat history.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent for accessing chat history.

    Returns:
        A list of chat message dictionaries.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    if debug:
        return agent.get_filtered_chat_history(False, False, False, from_timestamp=fromTimestamp)

    return agent.get_filtered_chat_history(from_timestamp=fromTimestamp)


@router.post("/{name}/chat", status_code=status.HTTP_201_CREATED)
async def send_chat_message(
    name: str,
    chat_msg: ChatMessage,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """
    Sends a user message to a character and gets a generated response.

    This endpoint handles the main chat interaction loop. It takes a user's
    message, processes it, and returns the character's reply.

    Args:
        name: The unique identifier for the character.
        chat_msg: The user's message payload. May include an optional
            ``base_timestamp`` (milliseconds since epoch) representing the
            virtual time of the conversation. When ``None`` the server uses
            the current system clock.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent for processing messages.
        llm_lock: A lock to ensure that LLM inference calls are serialized.

    Returns:
        A dictionary containing the role ("assistant"), the generated content,
        and ``total_tokens`` — the combined prompt and completion token count
        from the last inference call, which the UI surfaces as the current
        context fill level.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found")

    # Offload blocking LLM inference to a thread pool to prevent event loop starvation.
    async with llm_lock:
        bot_response = await asyncio.to_thread(
            agent.process_user_message, chat_msg.message, chat_msg.base_timestamp
        )

    return {
        "role": "assistant",
        "content": bot_response.content,
        "total_tokens": bot_response.total_tokens,
    }


@router.post("/{name}/chat/recreate", status_code=status.HTTP_201_CREATED)
async def recreate_chat_message(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """
    Regenerates the last AI-generated message in the chat history.

    This is useful for retrying a response if the previous one was unsatisfactory.
    It effectively deletes the last assistant message and creates a new one,
    operating on the exact same conversation history as before.

    Args:
        name: The unique identifier for the character.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent for message regeneration.
        llm_lock: A lock to ensure that LLM inference calls are serialized.

    Returns:
        A dictionary containing the role ("assistant"), the regenerated content,
        and ``total_tokens`` — the combined prompt and completion token count
        from the regeneration call, used by the UI to refresh the current
        context fill indicator.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    async with llm_lock:
        bot_response = await asyncio.to_thread(agent.recreate_last_message)

    return {
        "role": "assistant",
        "content": bot_response.content,
        "total_tokens": bot_response.total_tokens,
    }


@router.post("/{name}/chat/summarize", status_code=status.HTTP_201_CREATED)
async def summarize_chat(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """
    Triggers the generation of a background summary for context window management.
    The rolling window size is fixed at 5 messages.

    Args:
        name: The unique identifier for the character.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent.
        llm_lock: A lock to ensure that LLM inference calls are serialized.

    Returns:
        A dictionary containing a status message and ``total_tokens`` — the
        token count of the summarization inference call, or ``None`` when the
        history was still short enough to skip the call entirely.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    async with llm_lock:
        # We pass n=5 to create_summary to keep the last 5 messages unsummarized.
        summary_result = await asyncio.to_thread(agent.create_summary, n=5)

    return {
        "message": "Summary created.",
        "total_tokens": summary_result.total_tokens if summary_result is not None else None,
    }


@router.patch("/{name}/chat/{timestamp}")
async def update_chat_message(
    timestamp: int,
    payload: ChatMessageUpdate,
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Updates the textual content of an existing chat message identified by its timestamp.

    Args:
        timestamp: The Unix timestamp of the message to be updated.
        payload: Validation data containing the new message content.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message upon successful update.

    Raises:
        HTTPException: 404 if a message with the given timestamp is not found.
    """
    if chat_repo.update_message_content(timestamp, payload.content):
        return {"message": "Message updated."}
    raise HTTPException(status_code=404, detail="Message not found.")


@router.delete("/{name}/chat/{timestamp}")
async def delete_chat_message(
    timestamp: int,
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Deletes a specific message from the chat history using its timestamp.

    Args:
        timestamp: The Unix timestamp of the message to be deleted.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message upon successful deletion.

    Raises:
        HTTPException: 404 if a message with the given timestamp is not found.
    """
    if chat_repo.delete_user_message(timestamp):
        return {"message": "Message deleted."}
    raise HTTPException(status_code=404, detail="Message not found.")