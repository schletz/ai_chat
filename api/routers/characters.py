"""FastAPI router for managing character resources."""

from fastapi import APIRouter, Depends, HTTPException, status
from dependencies import get_character_repository, get_llm_service
from character_repository import CharacterRepository
from llm_service import LLMService
from schemas import (
    CharacterAppendTimestampPatch,
    CharacterCreate,
    CharacterEnableThinkingPatch,
    CharacterUpdate,
    CharacterVirtualClockPatch,
)

router = APIRouter(prefix="/characters")


@router.get("")
async def get_characters(
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, list]:
    """Retrieve all characters for the authenticated user.

    Returns:
        dict: A dictionary containing a list of character objects.
    """
    return {"characters": char_repo.data}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_character(
    char: CharacterCreate,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Create a new character with the provided configuration.

    Args:
        char: Validation data for the new character.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message upon successful creation.

    Raises:
        HTTPException: If a character with the same name already exists.
    """
    if char_repo.get_character_by_name(char.name) is not None:
        raise HTTPException(status_code=400, detail="Character already exists")

    char_repo.insert_character(
        name=char.name,
        character_name=char.character_name or "",
        user_name=char.user_name or "",
        system_prompt=char.system_prompt,
        intro=char.intro or "",
        plot_generation_prompt=char.plot_generation_prompt or "",
        sticky_note_pos=char.sticky_note_pos,
        append_timestamp=char.append_timestamp,
        reset_cache=char.reset_cache,
        full_history_for_last_n=char.full_history_for_last_n,
        full_history_for_last_n_plot_generation=char.full_history_for_last_n_plot_generation,
        cap_history=char.cap_history,
        idle_threshold_ms=char.idle_threshold_ms,
        time_scale=char.time_scale,
        temperature=char.temperature,
        min_p=char.min_p,
        top_p=char.top_p,
        top_k=char.top_k,
        repeat_penalty=char.repeat_penalty,
        frequency_penalty=char.frequency_penalty,
        presence_penalty=char.presence_penalty,
        max_tokens=char.max_tokens,
    )
    return {"message": f"Character {char.name} created."}


@router.put("/{name}")
async def update_character(
    name: str,
    update_data: CharacterUpdate,
    char_repo: CharacterRepository = Depends(get_character_repository),
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, str]:
    """Update the configuration of an existing character.

    Args:
        name: The unique identifier for the target character.
        update_data: Validation data containing updated fields.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message upon successful update.

    Raises:
        HTTPException: If the specified character is not found.
    """
    try:
        # exclude_unset=True ensures that only the fields that the client actually sent
        # are included in the dict (even if they are null/None).
        update_dict = update_data.model_dump(exclude_unset=True)
        
        char_repo.set_character_settings(
            character=name,
            **update_dict
        )
        llm_service.reset()

        return {"message": f"Character {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/append-timestamp")
async def patch_append_timestamp(
    name: str,
    payload: CharacterAppendTimestampPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Update only the append_timestamp flag for an existing character.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the new append_timestamp value.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message upon successful update.

    Raises:
        HTTPException: If the specified character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Character {name} not found")

    try:
        char_repo.set_character_settings(
            character=name,
            append_timestamp=payload.append_timestamp,
        )
        return {"message": f"Character {name} append_timestamp updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/thinking")
async def patch_enable_thinking(
    name: str,
    payload: CharacterEnableThinkingPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Update only the per-character reasoning (thinking) flag.

    The flag is read at inference time and toggles whether the model emits its
    reasoning output for this character's turns, replacing the former
    system-wide setting.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the new enable_thinking value.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message upon successful update.

    Raises:
        HTTPException: If the specified character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Character {name} not found")

    try:
        char_repo.set_character_settings(
            character=name,
            enable_thinking=payload.enable_thinking,
        )
        return {"message": f"Character {name} enable_thinking updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/virtual-clock")
async def patch_virtual_clock(
    name: str,
    payload: CharacterVirtualClockPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Store or clear the virtual clock anchor for an existing character.

    A ``null`` ``baseTimestamp`` removes the stored anchor so the chat view
    falls back to the system clock; otherwise the anchor pair is persisted in
    the character settings.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the virtual clock anchor pair.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message describing the resulting state.

    Raises:
        HTTPException: If the specified character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Character {name} not found")

    try:
        if payload.baseTimestamp is None:
            char_repo.clear_virtual_clock(name)
            return {"message": f"Virtual clock for {name} cleared."}

        char_repo.set_virtual_clock(name, payload.baseTimestamp, payload.anchorTimestamp or 0)
        return {"message": f"Virtual clock for {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.delete("/{name}")
async def delete_character(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Permanently remove a character and its associated chat history.

    Args:
        name: The unique identifier for the target character.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message upon successful deletion.

    Raises:
        HTTPException: If the specified character is not found.
    """
    if char_repo.delete_character(name):
        return {"message": f"Character {name} successfully deleted."}
    raise HTTPException(status_code=404, detail="Character not found.")