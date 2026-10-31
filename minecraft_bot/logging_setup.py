from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class SafeFormatter(logging.Formatter):
    def __init__(self, secrets: tuple[str, ...]):
        super().__init__()
        self.secrets = tuple(x for x in secrets if x)

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message += " [" + record.exc_info[0].__name__ + "]"
        for secret in self.secrets:
            message = message.replace(secret, "[REDACTED]")
        message = re.sub(r"(?i)Bearer\s+\S+", "Bearer [REDACTED]", message)
        return json.dumps(
            {
                "time": datetime.now(UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            },
            ensure_ascii=False,
        )


def configure(directory: Path, secrets: tuple[str, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        directory / "bot.jsonl", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(SafeFormatter(secrets))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def audit(event: str, user_id: int | None = None, outcome: str = "") -> None:
    logging.getLogger("audit").info("event=%s user_id=%s outcome=%s", event, user_id, outcome)
