from typing import Optional

from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Represents a request for user authentication."""

    username: str
    password: str


class CharacterCreate(BaseModel):
    """Schema definition for creating a new character profile."""

    name: str
    system_prompt: str
    send_with_timestamp: bool = True


class ChatMessage(BaseModel):
    """Schema definition for an outgoing chat message."""

    message: str


class CharacterUpdate(BaseModel):
    """Schema definition for updating existing character configuration."""

    system_prompt: Optional[str] = None
    send_with_timestamp: Optional[bool] = None


class ModelChangeRequest(BaseModel):
    """Represents a request to switch the active language model."""

    model_id: str