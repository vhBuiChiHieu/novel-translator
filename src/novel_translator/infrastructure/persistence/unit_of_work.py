from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

SessionFactory = Callable[[], Session]


class SqlAlchemyUnitOfWork:
    """Explicit transaction boundary used by application services."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnitOfWork:
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        assert self.session is not None
        if exc_type is None:
            self.session.commit()
        else:
            self.session.rollback()
        self.session.close()
