import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Create an async engine
async_engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
)

# Create a session maker
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db() -> AsyncSession:
    """
    Dependency to get a database session.
    """
    async with AsyncSessionLocal() as session:
        yield session
