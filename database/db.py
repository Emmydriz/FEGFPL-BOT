from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config.settings import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate SQLite table columns if missing
        from sqlalchemy import text
        for col_def in [
            "ALTER TABLE users ADD COLUMN current_season VARCHAR(50) DEFAULT '2026/2027'",
            "ALTER TABLE users ADD COLUMN membership_status VARCHAR(50) DEFAULT 'ACTIVE'",
            "ALTER TABLE users ADD COLUMN renewal_deadline DATETIME",
            "ALTER TABLE users ADD COLUMN renewal_payment_status VARCHAR(50) DEFAULT 'NOT_SUBMITTED'"
        ]:
            try:
                await conn.execute(text(col_def))
            except Exception:
                pass

    # Sync active receiving payment account config from .env settings
    from database.repository import sync_payment_account_from_settings
    async with get_db_session() as session:
        await sync_payment_account_from_settings(session)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
