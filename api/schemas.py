from pydantic import BaseModel
from typing import Optional

class AuthRequest(BaseModel):
    """Request for user authentication."""
    username: str
    password: str

class CharacterCreate(BaseModel):
    """Schema for creating a new character."""
    name: str
    system_prompt: str
    send_with_timestamp: bool = True

class ChatMessage(BaseModel):
    """Schema for a chat message to be sent."""
    message: str

class CharacterUpdate(BaseModel):
    """Schema for updating existing character settings."""
    system_prompt: Optional[str] = None
    send_with_timestamp: Optional[bool] = None

class ModelChangeRequest(BaseModel):
    """Request for switching the active LLM model."""
    model_id: str
