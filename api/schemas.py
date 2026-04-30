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
    intro: Optional[str] = None
    plot: Optional[str] = None
    send_with_timestamp: bool = True
    idle_threshold_ms: int = 3600000
    temperature: Optional[float] = None
    min_p: Optional[float] = None
    top_p: Optional[float] = None
    repeat_penalty: Optional[float] = None
    max_tokens: Optional[int] = None
    auto_summarize_tokens: Optional[int] = None


class ChatMessage(BaseModel):
    """Schema definition for an outgoing chat message."""

    message: str
    base_timestamp: Optional[int] = None


class CharacterUpdate(BaseModel):
    """Schema definition for updating existing character configuration."""

    system_prompt: Optional[str] = None
    intro: Optional[str] = None
    plot: Optional[str] = None
    send_with_timestamp: Optional[bool] = None
    idle_threshold_ms: Optional[int] = None
    temperature: Optional[float] = None
    min_p: Optional[float] = None
    top_p: Optional[float] = None
    repeat_penalty: Optional[float] = None
    max_tokens: Optional[int] = None
    auto_summarize_tokens: Optional[int] = None


class CharacterSendWithTimestampPatch(BaseModel):
    """Schema definition for patching only the send_with_timestamp flag."""

    send_with_timestamp: bool


class CharacterSummaryPatch(BaseModel):
    """Schema definition for patching the rolling chat summary.

    An empty ``text`` removes the stored summary entirely so the rolling
    window expands again to cover the full chat history.
    """

    text: str


class CharacterPlotPatch(BaseModel):
    """Schema definition for patching the daily plot of a character.

    An empty ``plot`` removes the stored plot entirely so no plot context is
    injected into the chat.
    """

    plot: str


class ChatMessageUpdate(BaseModel):
    """Schema definition for editing the content of an existing chat message."""

    content: str


class ModelChangeRequest(BaseModel):
    """Represents a request to switch the active language model."""

    model_id: str
    n_gpu_layers: Optional[int] = None