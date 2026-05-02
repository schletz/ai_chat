import jwt
from fastapi import Request, HTTPException, status, Depends
import datetime
from user_repository import UserRepository
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from character_agent import CharacterAgent
import asyncio

def get_config_manager(request: Request):
    return request.app.state.config_manager

def get_llm_service(request: Request):
    return request.app.state.llm_service

def get_tool_collection(request: Request):
    return request.app.state.llm_tool_collection

def get_llm_lock(request: Request) -> asyncio.Lock:
    return request.app.state.llm_lock

def get_data_dir(request: Request) -> str:
    return request.app.state.data_dir

def get_secret_key(request: Request) -> str:
    return request.app.state.secret_key

def get_algorithm(request: Request) -> str:
    return request.app.state.algorithm

def get_user_repository(data_dir: str = Depends(get_data_dir)) -> UserRepository:
    return UserRepository(data_dir)

async def get_current_user(
    request: Request,
    secret_key: str = Depends(get_secret_key),
    algorithm: str = Depends(get_algorithm)
) -> str:
    """
    Abhängigkeitsinjektion (Dependency Injection):
    Diese Funktion liest das JWT (JSON Web Token) sicher aus dem HttpOnly-Cookie.
    So muss die Authentifizierungslogik nicht in jedem Router-Endpunkt wiederholt werden.
    Wird bei fehlendem Token automatisch einen 401 Unauthorized Fehler an den Client werfen.
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
    return CharacterRepository(data_dir, username)

def get_chat_repository(
    name: str,
    data_dir: str = Depends(get_data_dir),
    username: str = Depends(get_current_user)
) -> ChatRepository:
    return ChatRepository(data_dir, username, name)

def get_character_agent(
    char_repo: CharacterRepository = Depends(get_character_repository),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service = Depends(get_llm_service),
    tool_coll = Depends(get_tool_collection)
) -> CharacterAgent:
    return CharacterAgent(char_repo, chat_repo, llm_service, tool_coll)
