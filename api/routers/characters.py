"""FastAPI router for managing character resources."""

from fastapi import APIRouter, Depends, HTTPException, status
from dependencies import get_character_repository
from character_repository import CharacterRepository
from schemas import (
    CharacterCreate,
    CharacterPlotPatch,
    CharacterSendWithTimestampPatch,
    CharacterSummaryPatch,
    CharacterUpdate,
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
        system_prompt=char.system_prompt,
        intro=char.intro or "",
        plot=char.plot or "",
        send_with_timestamp=char.send_with_timestamp,
        idle_threshold_ms=char.idle_threshold_ms,
        temperature=char.temperature,
        min_p=char.min_p,
        top_p=char.top_p,
        repeat_penalty=char.repeat_penalty,
        max_tokens=char.max_tokens,
        auto_summarize_tokens=char.auto_summarize_tokens,
    )
    return {"message": f"Character {char.name} created."}


@router.put("/{name}")
async def update_character(
    name: str,
    update_data: CharacterUpdate,
    char_repo: CharacterRepository = Depends(get_character_repository),
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
        return {"message": f"Character {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/send-with-timestamp")
async def patch_send_with_timestamp(
    name: str,
    payload: CharacterSendWithTimestampPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Update only the send_with_timestamp flag for an existing character.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the new send_with_timestamp value.
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
            send_with_timestamp=payload.send_with_timestamp,
        )
        return {"message": f"Character {name} send_with_timestamp updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/summary")
async def patch_summary(
    name: str,
    payload: CharacterSummaryPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Update or clear the rolling chat summary for an existing character.

    An empty ``text`` removes the stored summary entirely so the chat view
    expands back to the full history; a non-empty value overwrites the
    existing summary while keeping its timestamp anchor.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the new summary text.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message describing the resulting state.

    Raises:
        HTTPException: If the specified character is not found.
    """
    character = char_repo.get_character_by_name(name)
    if character is None:
        raise HTTPException(status_code=404, detail=f"Character {name} not found")

    try:
        if payload.text.strip() == "":
            char_repo.clear_summary(name)
            return {"message": f"Summary for {name} cleared."}

        existing = character.get("summary") or {}
        timestamp = int(existing.get("timestamp", 0))
        char_repo.set_summary(name, payload.text, timestamp)
        return {"message": f"Summary for {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/{name}/plot")
async def patch_plot(
    name: str,
    payload: CharacterPlotPatch,
    char_repo: CharacterRepository = Depends(get_character_repository),
) -> dict[str, str]:
    """Update or clear the daily plot for an existing character.

    The plot describes the intended storyline of the day and is injected into
    the chat after the intro and the rolling summary. An empty ``plot`` removes
    the stored plot entirely.

    Args:
        name: The unique identifier for the target character.
        payload: Validation data containing the new plot text.
        char_repo: Repository instance for persistence operations.

    Returns:
        dict: Confirmation message describing the resulting state.

    Raises:
        HTTPException: If the specified character is not found.
    """
    if char_repo.get_character_by_name(name) is None:
        raise HTTPException(status_code=404, detail=f"Character {name} not found")

    try:
        char_repo.set_character_settings(character=name, plot=payload.plot)
        if payload.plot.strip() == "":
            return {"message": f"Plot for {name} cleared."}
        return {"message": f"Plot for {name} updated."}
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