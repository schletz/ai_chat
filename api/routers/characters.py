from fastapi import APIRouter, Depends, HTTPException, status
from dependencies import get_character_repository
from character_repository import CharacterRepository
from schemas import CharacterCreate, CharacterUpdate

router = APIRouter(prefix="/characters")

@router.get("")
async def get_characters(char_repo: CharacterRepository = Depends(get_character_repository)):
    """Lists all characters for the authenticated user."""
    return {"characters": char_repo.data}

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_character(
    char: CharacterCreate,
    char_repo: CharacterRepository = Depends(get_character_repository)
):
    """Creates a new character. Checks for duplicates."""
    if char_repo.get_character_by_name(char.name) is not None:
        raise HTTPException(status_code=400, detail="Character already exists")

    char_repo.insert_character(
        char.name,
        char.system_prompt,
        char.send_with_timestamp,
    )
    return {"message": f"Character {char.name} created."}

@router.put("/{name}")
async def update_character(
    name: str,
    update_data: CharacterUpdate,
    char_repo: CharacterRepository = Depends(get_character_repository)
):
    """Updates system prompt or timestamp setting of a character."""
    try:
        char_repo.set_character_settings(
            character=name,
            system_prompt=update_data.system_prompt,
            send_with_timestamp=update_data.send_with_timestamp,
        )
        return {"message": f"Character {name} updated."}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/{name}")
async def delete_character(
    name: str,
    char_repo: CharacterRepository = Depends(get_character_repository)
):
    """Deletes a character and its associated data."""
    if char_repo.delete_character(name):
        return {"message": f"Character {name} successfully deleted."}
    raise HTTPException(status_code=404, detail="Character not found.")
