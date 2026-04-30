import jwt
from fastapi import Request, HTTPException, status, Depends
import datetime
from user_repository import UserRepository
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from character_agent import CharacterAgent
import asyncio


def get_config_manager(request: Request):
    """Retrieve the application configuration manager."""
    return request.app.state.config_manager


def get_llm_service(request: Request):
    """Retrieve the LLM service instance."""
    return request.app.state.llm_service


def get_tool_collection(request: Request):
    """Retrieve the LLM tool collection instance."""
    return request.app.state.llm_tool_collection


def get_llm_lock(request: Request) -> asyncio.Lock:
    """Retrieve the asynchronous lock for LLM operations."""
    return request.app.state.llm_lock


def get_data_dir(request: Request) -> str:
    """Retrieve the application data directory path."""
    return request.app.state.data_dir


def get_secret_key(request: Request) -> str:
    """Retrieve the secret key used for JWT signing and verification."""
    return request.app.state.secret_key


def get_algorithm(request: Request) -> str:
    """Retrieve the algorithm used for JWT encoding and decoding."""
    return request.app.state.algorithm


def get_user_repository(data_dir: str = Depends(get_data_dir)) -> UserRepository:
    """Initialize and retrieve a user repository instance.

    Args:
        data_dir: Path to the application data directory.

    Returns:
        An initialized UserRepository instance.
    """
    return UserRepository(data_dir)


async def get_current_user(
    request: Request,
    secret_key: str = Depends(get_secret_key),
    algorithm: str = Depends(get_algorithm)
) -> str:
    """Extract and validate the current user from the JWT cookie.

    Args:
        request: The FastAPI request object containing cookies.
        secret_key: Secret key for decoding the token.
        algorithm: Algorithm used to encode/decode the token.

    Returns:
        The username extracted from the valid token payload.

    Raises:
        HTTPException: If the token is missing, invalid, or expired.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid or expired"
        )


def get_character_repository(
    data_dir: str = Depends(get_data_dir),
    username: str = Depends(get_current_user)
) -> CharacterRepository:
    """Initialize and retrieve a character repository instance.

    Args:
        data_dir: Path to the application data directory.
        username: The authenticated username for context isolation.

    Returns:
        An initialized CharacterRepository instance.
    """
    return CharacterRepository(data_dir, username)


def get_chat_repository(
    name: str,
    data_dir: str = Depends(get_data_dir),
    username: str = Depends(get_current_user)
) -> ChatRepository:
    """Initialize and retrieve a chat repository instance.

    Args:
        name: The identifier for the specific chat session.
        data_dir: Path to the application data directory.
        username: The authenticated username for context isolation.

    Returns:
        An initialized ChatRepository instance.
    """
    return ChatRepository(data_dir, username, name)


def get_character_agent(
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service = Depends(get_llm_service),
    tool_coll = Depends(get_tool_collection)
) -> CharacterAgent:
    """Initialize and retrieve a character agent instance.

    Args:
        char_repo: The repository for managing character data.
        chat_repo: The repository for managing chat history.
        llm_service: The service handling large language model interactions.
        tool_coll: The collection of available tools for the agent.

    Returns:
        An initialized CharacterAgent instance.
    """
    return CharacterAgent(char_repo, chat_repo, llm_service, tool_coll)