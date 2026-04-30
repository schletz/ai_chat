from typing import Optional

from pydantic import BaseModel


class AuthRequest(BaseModel):
    """Represents a request for user authentication."""

    username: str
    password: str


class CharacterCreate(BaseModel):
    """Schema definition for creating a new character profile."""

    name: str
    character_name: Optional[str] = None
    user_name: Optional[str] = None
    system_prompt: str
    intro: Optional[str] = None
    plot_generation_prompt: Optional[str] = None
    sticky_note: Optional[str] = None
    sticky_note_pos: Optional[int] = None
    append_timestamp: bool = True
    reset_cache: bool = False
    full_history_for_last_n: Optional[int] = None
    full_history_for_last_n_plot_generation: Optional[int] = None
    cap_history: Optional[int] = None
    idle_threshold_ms: int = 3600000
    time_scale: Optional[float] = None
    temperature: Optional[float] = None
    min_p: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    max_tokens: Optional[int] = None


class ChatMessage(BaseModel):
    """Schema definition for a user chat message (sent or inserted).

    ``base_timestamp`` (milliseconds since epoch) is mandatory: the frontend
    always sends the current in-world time, so the server never has to guess a
    clock. It is recorded as the message's ``virtual_ts`` and, for the inference
    endpoint, also drives the in-world time of the turn.
    """

    message: str
    base_timestamp: int


class DirectorMessage(BaseModel):
    """Schema definition for a director instruction steering the roleplay.

    ``base_timestamp`` (milliseconds since epoch) is mandatory: it is recorded
    as the inserted message's ``virtual_ts`` and appended as ``<timestamp>``
    metadata so the in-world time is preserved.
    """

    message: str
    base_timestamp: int


class PlotMessage(BaseModel):
    """Schema definition for manually inserting a plot steering the roleplay.

    Mirrors :class:`DirectorMessage` but the text is stored wrapped in ``<director>``
    tags, matching the format of auto-generated plots.

    ``base_timestamp`` is the optional virtual-clock anchor in milliseconds
    since the epoch. When provided it is recorded as the inserted message's
    ``virtual_ts`` so the in-world time is preserved. When ``None`` only the
    wall-clock timestamp is stored.
    """

    message: str
    base_timestamp: Optional[int] = None


class AssistantMessageInsert(BaseModel):
    """Schema definition for manually inserting an assistant message.

    Lets the user author an assistant turn directly to steer the roleplay. The
    message is appended to the history without triggering inference.

    ``base_timestamp`` (milliseconds since epoch) is mandatory: it is recorded
    as the inserted message's ``virtual_ts`` so the in-world time is preserved.
    """

    message: str
    base_timestamp: int


class PlotGenerateRequest(BaseModel):
    """Schema definition for triggering an auto-generated director plot.

    ``base_timestamp`` (milliseconds since epoch) is mandatory: the agent
    appends the corresponding in-world time to the director system prompt as
    additional context for the plot generation.
    """

    base_timestamp: int


class AssistantMessageRequest(BaseModel):
    """Schema definition for requesting an additional assistant turn.

    ``base_timestamp`` (milliseconds since epoch) is mandatory: it resolves the
    in-world time of the turn (injected as ``<timestamp>`` metadata into the
    agent instruction and used to resolve the sticky note's ``${time}``
    placeholder).
    """

    base_timestamp: int


class CharacterUpdate(BaseModel):
    """Schema definition for updating existing character configuration."""

    character_name: Optional[str] = None
    user_name: Optional[str] = None
    system_prompt: Optional[str] = None
    intro: Optional[str] = None
    plot_generation_prompt: Optional[str] = None
    sticky_note: Optional[str] = None
    sticky_note_pos: Optional[int] = None
    append_timestamp: Optional[bool] = None
    reset_cache: Optional[bool] = None
    full_history_for_last_n: Optional[int] = None
    full_history_for_last_n_plot_generation: Optional[int] = None
    cap_history: Optional[int] = None
    idle_threshold_ms: Optional[int] = None
    time_scale: Optional[float] = None
    temperature: Optional[float] = None
    min_p: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    max_tokens: Optional[int] = None


class CharacterAppendTimestampPatch(BaseModel):
    """Schema definition for patching only the append_timestamp flag."""

    append_timestamp: bool


class CharacterEnableThinkingPatch(BaseModel):
    """Schema definition for patching only the per-character reasoning flag."""

    enable_thinking: bool


class CharacterVirtualClockPatch(BaseModel):
    """Schema definition for patching the per-character virtual clock anchor.

    ``baseTimestamp`` is the user-defined in-world anchor in milliseconds and
    ``anchorTimestamp`` the wall-clock moment that anchor was applied. Sending
    ``null`` for ``baseTimestamp`` clears the stored clock so the chat falls
    back to the system time.
    """

    baseTimestamp: Optional[int] = None
    anchorTimestamp: Optional[int] = None


class ChatMessageUpdate(BaseModel):
    """Schema definition for editing the content of an existing chat message."""

    content: str


class LastSceneMessagePatch(BaseModel):
    """Schema definition for toggling a message's ``last_scene_message`` flag.

    The flag marks the boundary from which the current scene's history is read.
    """

    last_scene_message: bool


class ModelChangeRequest(BaseModel):
    """Represents a request to switch the active language model."""

    model_id: str
    n_gpu_layers: Optional[int] = None