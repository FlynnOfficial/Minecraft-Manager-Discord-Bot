from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo


class State(StrEnum):
    ONLINE = "Online"
    OFFLINE = "Offline"
    STARTING = "Iniciando"
    STOPPING = "Desligando"
    UNAVAILABLE = "Indisponível"


def integer(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def timestamp(value: object, timezone: ZoneInfo) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        date = datetime.fromisoformat(value)
    except ValueError:
        try:
            date = datetime.strptime(value, "%Y/%m/%d, %H:%M:%S")
        except ValueError:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone)
    return date.astimezone(UTC)


@dataclass(frozen=True)
class LiveStatus:
    online: int | None
    maximum: int | None
    names: tuple[str, ...] | None
    version: str | None


@dataclass(frozen=True)
class Snapshot:
    state: State = State.UNAVAILABLE
    crafty_ok: bool = False
    detail: str = "Crafty indisponível"
    running: bool | None = None
    online: int | None = None
    maximum: int | None = None
    names: tuple[str, ...] | None = None
    version: str | None = None
    started: datetime | None = None
    observed: datetime | None = None
    collected: datetime | None = None
    fresh: bool = False
    live: LiveStatus | None = None
    api_online: int | None = None
    waiting: bool = False
    graceful_stop: bool = False
