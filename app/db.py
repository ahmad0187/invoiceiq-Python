from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from . import config

config.DATA_DIR.mkdir(parents=True, exist_ok=True)
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args)


def init_db() -> None:
    from . import models  # noqa: F401  (registers the tables)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
