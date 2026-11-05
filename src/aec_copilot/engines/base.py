"""Engine SPI. Implementations must preserve the public unit/error/transaction contract."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any


class Transaction(ABC):
    @abstractmethod
    def __enter__(self) -> "Transaction": ...

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


class Engine(ABC):
    name: str
    backend: str

    @abstractmethod
    def transaction(self) -> Transaction: ...

    @abstractmethod
    def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def snapshot(self) -> list[dict[str, Any]]: ...

    def capture(self, output: str | Path, *, title: str = "AEC Copilot") -> str:
        from ..render import render_elements
        return render_elements(self.snapshot(), output, title=f"{title} · {self.backend.upper()}")


class CallbackTransaction(Transaction):
    """Transaction helper for adapters with native begin/commit/rollback hooks."""

    def __init__(self, begin: Callable[[], None], commit: Callable[[], None], rollback: Callable[[], None]) -> None:
        self._begin, self._commit, self._rollback = begin, commit, rollback
        self._finished = False

    def __enter__(self) -> "CallbackTransaction":
        self._begin()
        return self

    def commit(self) -> None:
        if not self._finished:
            self._commit()
            self._finished = True

    def rollback(self) -> None:
        if not self._finished:
            self._rollback()
            self._finished = True
