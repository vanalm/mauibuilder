import os
from contextlib import contextmanager

from sqlalchemy import create_engine as create_engine_
from sqlalchemy.orm import sessionmaker
from server.configmanager import config

__database_url = config.get("DATABASE_URL")

assert __database_url, "DATABASE_URL environment variable must be set"

engine = create_engine_(__database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session():
    """
    Context manager that yields a SQLAlchemy session for our single database.
    After the 'with' block, it closes the session automatically.
    """

    assert engine
    assert SessionLocal

    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()
