"""Engine / session factory. The rest of the app never touches the engine directly."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite"):
        # FastAPI serves requests from a thread pool.
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)

    if engine.dialect.name == "sqlite":
        # SQLite ignores foreign keys unless asked; Postgres always enforces them.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    db: Session = request.app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()
