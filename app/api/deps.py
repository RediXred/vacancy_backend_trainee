from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import async_session_maker
from typing import AsyncGenerator


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
