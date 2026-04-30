import asyncio
import time
import logging
from datetime import datetime
from fastapi import FastAPI

from user_repository import UserRepository
from character_repository import CharacterRepository
from chat_repository import ChatRepository
from character_agent import CharacterAgent

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Executes background tasks, such as automatically triggering agent responses."""

    def __init__(self, llm_lock: asyncio.Lock, delay_sec: int):
        self.llm_lock = llm_lock
        self.delay_sec = delay_sec
        self.is_busy = False

    async def run(self, app: FastAPI, data_dir: str):
        """Starts the worker's infinite loop. Prevents duplicate executions."""
        if self.is_busy:
            logger.warning("BackgroundWorker is already running. Start aborted.")
            return

        self.is_busy = True
        logger.info(f"BackgroundWorker started (interval: {self.delay_sec} seconds).")

        try:
            while True:
                await asyncio.sleep(self.delay_sec)

                try:
                    user_repo = UserRepository(data_dir)
                    current_timestamp = int(time.time() * 1000)

                    for username in user_repo.get_users():
                        char_repo = CharacterRepository(data_dir, username)

                        for char_name in char_repo.get_characters():
                            chat_repo = ChatRepository(data_dir, username, char_name)

                            agent = CharacterAgent(
                                character_repo=char_repo,
                                chat_repo=chat_repo,
                                llm_service=app.state.llm_service,
                                tool_coll=app.state.llm_tool_collection,
                            )

                            if agent.should_initiate_response(current_timestamp):
                                async with self.llm_lock:
                                    await asyncio.to_thread(agent.initiate_response, datetime.now())

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(f"Error within BackgroundWorker loop: {e}")

        except asyncio.CancelledError:
            logger.info("BackgroundWorker requested to stop (Cancelled).")
        finally:
            self.is_busy = False
            logger.info("BackgroundWorker stopped.")