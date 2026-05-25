"""Storage adapters for run directories."""

from stag.storage.base import RunStore
from stag.storage.jsonl import JsonlRunStore

__all__ = ["RunStore", "JsonlRunStore", "SqliteRunStore"]


def __getattr__(name: str):
    if name == "SqliteRunStore":
        from stag.storage.sqlite import SqliteRunStore

        return SqliteRunStore
    raise AttributeError(name)
