from __future__ import annotations

import json
import os
from pathlib import Path
from typing import IO


class Store:
    """Small durable journal; a corrupt file fails closed instead of forgetting a POST."""

    def __init__(self, directory: Path, scope: dict[str, str | int]):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "state.json"
        self.value: dict = {"schema": 1, "scope": scope, "panel_id": None, "pending": None}
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(loaded, dict)
                or loaded.get("schema") != 1
                or loaded.get("scope") != scope
            ):
                raise ValueError("Estado invalido ou configuracao alterada; consulte README.")
            if loaded.get("panel_id") is not None and type(loaded["panel_id"]) is not int:
                raise ValueError("Estado do painel invalido.")
            pending = loaded.get("pending")
            if pending is not None and (
                not isinstance(pending, dict)
                or pending.get("action") not in {"start_server", "stop_server"}
                or type(pending.get("sent_at")) not in {int, float}
            ):
                raise ValueError("Diario de operacao invalido.")
            self.value = loaded

    def set(self, **changes: object) -> None:
        value = self.value | changes
        temporary = self.path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        self.value = value


class InstanceLock:
    """OS-released lock prevents duplicate monitors/panels in one installation."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "instance.lock"
        self.handle: IO[bytes] | None = None

    def __enter__(self) -> InstanceLock:
        self.handle = self.path.open("a+b")
        try:
            if os.fstat(self.handle.fileno()).st_size == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            raise RuntimeError("Outra instancia do bot esta em execucao.") from None
        return self

    def __exit__(self, *args: object) -> None:
        if self.handle:
            self.handle.close()
