import sys
import asyncio
from src.infra.config import settings
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())



class DatabaseAsync:
    def __init__(self):
        self.engine = self._create_engine()
        self._session_maker = async_sessionmaker(bind=self.engine)

    def _create_engine(self):
        return create_async_engine(
            url=settings.URL_DB, echo=True, poolclass=pool.StaticPool, future=True
        )

    @asynccontextmanager
    async def session(self):
        session = self._session_maker()
        session.sync_session.autoflush = False
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


database = DatabaseAsync()
