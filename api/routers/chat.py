from fastapi import APIRouter, Depends, HTTPException, status
import asyncio
from dependencies import get_character_agent, get_chat_history, get_chat_repository, get_character_repository, get_llm_lock, get_llm_service
from character_agent import CharacterAgent
from chat_history import ChatHistory
from chat_repository import ChatRepository
from character_repository import CharacterRepository
from llm_service import LLMService
from schemas import AssistantMessageInsert, AssistantMessageRequest, ChatMessage, ChatMessageUpdate, DirectorMessage, LastSceneMessagePatch, PlotGenerateRequest, PlotMessage

router = APIRouter(prefix="/characters")


@router.get("/{name}/chat")
async def get_chat(
    name: str,
    base_timestamp: int,
    fromTimestamp: int = 0,
    debug: bool = False,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_history: ChatHistory = Depends(get_chat_history)
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
        base_timestamp: Mandatory virtual time in milliseconds since the epoch,
            always forwarded from the frontend, used to resolve the ``${time}``
            placeholder of the injected sticky note so the rendered bubble
            matches what the model sees.
        char_repo: Dependency-injected character repository.
        chat_history: Dependency-injected chat history assembler.

    Returns:
        A list of chat message dictionaries.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    return chat_history.get_history(fromTimestamp=fromTimestamp, debug=debug, base_timestamp=base_timestamp)


@router.get("/{name}/chat/context")
async def get_chat_context(
    name: str,
    base_timestamp: int | None = None,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_history: ChatHistory = Depends(get_chat_history)
):
    """
    Returns the assembled context of the current chat session for inspection.

    The context combines the optional character intro and the rolling-summary
    view of the chat history into a single XML-flavored string. The system
    prompt is intentionally excluded so the output matches exactly what
    ``generate_plot`` sees. It is meant purely for debugging and analysis in the
    frontend; no inference is triggered, so the LLM lock is not required.
    Assembly is offloaded to a thread to keep the event loop responsive.

    Args:
        name: The unique identifier for the character.
        base_timestamp: Optional virtual time in milliseconds since the epoch,
            forwarded from the frontend. When provided the corresponding in-world
            date and time is prepended to the context.
        char_repo: Dependency-injected character repository.
        chat_history: Dependency-injected chat history assembler.

    Returns:
        A dictionary with a single ``context`` key holding the context string.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    context = await asyncio.to_thread(
        chat_history.get_context,
        include_system_prompt=False,
        include_intro=False,
        base_timestamp=base_timestamp,
    )
    return {"context": context}


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
        chat_msg: The user's message payload. Includes the mandatory
            ``base_timestamp`` (milliseconds since epoch) representing the
            current in-world time, always supplied by the frontend.
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


@router.post("/{name}/chat/director", status_code=status.HTTP_201_CREATED)
async def add_director_chat_message(
    name: str,
    director_msg: DirectorMessage,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Adds a director instruction to the chat history without triggering inference.

    Director messages let the user steer the roleplay like a director giving
    stage directions. The instruction is stored as an agent message and only
    influences the next generated assistant response; no LLM call is made here,
    so the inference lock is not required.

    Args:
        name: The unique identifier for the character.
        director_msg: The director instruction payload.
        char_repo: Dependency-injected character repository.
        chat_history: Dependency-injected chat history.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo.add_director_message(
        director_msg.message.strip(),
        virtual_ts=director_msg.base_timestamp,
    )
    return {"message": "Director message added."}


@router.post("/{name}/chat/plot/insert", status_code=status.HTTP_201_CREATED)
async def insert_plot_chat_message(
    name: str,
    plot_msg: PlotMessage,
    char_repo: CharacterRepository = Depends(get_character_repository),
):
    """
    Stores a manually authored plot as the character's sticky note.

    The text overwrites the character's ``sticky_note`` property, which is
    injected near the end of the context on every turn. An empty message clears
    the sticky note. No LLM call is made here, so the inference lock is not
    required.

    Args:
        name: The unique identifier for the character.
        plot_msg: The plot payload.
        char_repo: Dependency-injected character repository.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    char_repo.set_sticky_note(name, plot_msg.message)
    return {"message": "Plot message added."}


@router.post("/{name}/chat/plot/generate", status_code=status.HTTP_201_CREATED)
async def generate_director_plot(
    name: str,
    plot_req: PlotGenerateRequest,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """
    Generates a director plot and stores it as a director message.

    The agent acts as a director: it derives a creative plot instruction from
    the current context via a dedicated LLM call and stores it as a director
    message. No assistant turn is produced; the plot only shapes the next
    generated assistant response. Because the director inference runs here, the
    LLM lock is required.

    Args:
        name: The unique identifier for the character.
        plot_req: The plot-generation payload. Includes the mandatory
            ``base_timestamp`` (milliseconds since epoch) representing the
            current in-world time, which is appended to the director system
            prompt. Always supplied by the frontend.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent.
        llm_lock: A lock to ensure that LLM inference calls are serialized.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    async with llm_lock:
        await asyncio.to_thread(
            agent.generate_plot, plot_req.base_timestamp
        )

    return {"message": "Plot added."}


@router.post("/{name}/chat/assistant", status_code=status.HTTP_201_CREATED)
async def request_assistant_chat_message(
    name: str,
    assistant_req: AssistantMessageRequest,
    regenerate: bool = False,
    char_repo: CharacterRepository = Depends(get_character_repository),
    agent: CharacterAgent = Depends(get_character_agent),
    llm_lock: asyncio.Lock = Depends(get_llm_lock)
):
    """
    Requests an assistant turn for the chat history.

    Depending on ``regenerate`` this either replaces the last AI-generated
    message (useful for retrying an unsatisfactory response) or appends an
    additional assistant message on top of the existing history. In both cases
    the response is produced from the same conversation context as before.

    Args:
        name: The unique identifier for the character.
        regenerate: If True, deletes the last assistant message and recreates
            it. If False, requests an additional assistant message without
            removing anything.
        assistant_req: The request payload. Includes the mandatory
            ``base_timestamp`` (milliseconds since epoch) representing the
            current in-world time, always supplied by the frontend. When
            ``regenerate`` is False it is injected as ``<timestamp>`` metadata
            into the agent instruction.
        char_repo: Dependency-injected character repository.
        agent: Dependency-injected character agent for message generation.
        llm_lock: A lock to ensure that LLM inference calls are serialized.

    Returns:
        A dictionary containing the role ("assistant"), the generated content,
        and ``total_tokens`` — the combined prompt and completion token count
        from the inference call, used by the UI to refresh the current context
        fill indicator.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    async with llm_lock:
        bot_response = await asyncio.to_thread(
            agent.request_assistant_message, regenerate, assistant_req.base_timestamp
        )

    return {
        "role": "assistant",
        "content": bot_response.content,
        "total_tokens": bot_response.total_tokens,
    }


@router.post("/{name}/chat/assistant/insert", status_code=status.HTTP_201_CREATED)
async def insert_assistant_chat_message(
    name: str,
    assistant_msg: AssistantMessageInsert,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Inserts a manually authored assistant message without triggering inference.

    This lets the user steer the roleplay by writing an assistant turn directly,
    for example to set up a scene or correct the model's direction. The message
    is appended to the chat history as a regular assistant message; no LLM call
    is made here, so the inference lock is not required.

    Args:
        name: The unique identifier for the character.
        assistant_msg: The assistant message payload.
        char_repo: Dependency-injected character repository.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo.add_assistant_message(assistant_msg.message.strip(), virtual_ts=assistant_msg.base_timestamp)
    return {"message": "Assistant message added."}


@router.post("/{name}/chat/user/insert", status_code=status.HTTP_201_CREATED)
async def insert_user_chat_message(
    name: str,
    chat_msg: ChatMessage,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
):
    """
    Inserts a user message without triggering inference.

    This appends the user's turn to the chat history but, unlike the main
    ``POST /{name}/chat`` endpoint, does not request a generated reply. It lets
    the user pre-seed the conversation to steer the next assistant response. No
    LLM call is made here, so the inference lock is not required. Unlike a sent
    message, no ``<timestamp>`` metadata is attached; only the virtual timestamp
    is recorded.

    Args:
        name: The unique identifier for the character.
        chat_msg: The user message payload. Includes the mandatory
            ``base_timestamp`` (milliseconds since epoch) recorded as the
            message's virtual timestamp.
        char_repo: Dependency-injected character repository.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    chat_repo.add_user_message(chat_msg.message.strip(), virtual_ts=chat_msg.base_timestamp)
    return {"message": "User message added."}


@router.patch("/{name}/chat/{timestamp}")
async def update_chat_message(
    timestamp: int,
    payload: ChatMessageUpdate,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service: LLMService = Depends(get_llm_service),
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
    if not chat_repo.update_message_content(timestamp, payload.content):
        raise HTTPException(status_code=404, detail="Message not found.")
    llm_service.reset()
    return {"message": "Message updated."}


@router.patch("/{name}/chat/{timestamp}/scene")
async def set_last_scene_message(
    timestamp: int,
    payload: LastSceneMessagePatch,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Sets or clears the ``last_scene_message`` flag of a chat message.

    The flag marks the boundary from which the current scene's history is read,
    letting the user start the effective history at a chosen message. No LLM
    call is made here, so the inference lock is not required.

    Args:
        timestamp: The Unix timestamp of the message to be updated.
        payload: Validation data containing the desired flag value.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message upon successful update.

    Raises:
        HTTPException: 404 if a message with the given timestamp is not found.
    """
    if not chat_repo.set_last_scene_message(timestamp, payload.last_scene_message):
        raise HTTPException(status_code=404, detail="Message not found.")
    llm_service.reset()
    return {"message": "Message updated."}


@router.delete("/{name}/chat/messages")
async def delete_all_chat_messages(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service: LLMService = Depends(get_llm_service),
):
    """
    Deletes the entire chat history for a specific character.

    Removes every stored message at once, leaving an empty history. No LLM call
    is made here, so the inference lock is not required.

    Args:
        name: The unique identifier for the character.
        char_repo: Dependency-injected character repository.
        chat_repo: Dependency-injected chat repository.

    Returns:
        A confirmation message including the number of deleted messages.

    Raises:
        HTTPException: 404 if the character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail="Character not found.")

    deleted = chat_repo.delete_all_messages()
    llm_service.reset()
    return {"message": "Chat history cleared.", "deleted": deleted}


@router.delete("/{name}/chat/{timestamp}")
async def delete_chat_message(
    timestamp: int,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service: LLMService = Depends(get_llm_service),
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
    if not chat_repo.delete_message(timestamp):
        raise HTTPException(status_code=404, detail="Message not found.")
    llm_service.reset()
    return {"message": "Message deleted."}