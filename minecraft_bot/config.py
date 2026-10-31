from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    discord_token: str = field(repr=False)
    crafty_token: str = field(repr=False)
    owner_id: int
    friend_id: int
    guild_id: int
    channel_id: int
    crafty_url: str
    server_id: str
    timezone: ZoneInfo
    data_dir: Path
    log_dir: Path
    ca_file: str | None = None
    fingerprint: str | None = None
    crafty_version: str = "nao_informada"
    status_host: str = "127.0.0.1"
    status_port: int = 25565
    poll_seconds: float = 30
    http_timeout: float = 10
    status_timeout: float = 5
    stats_max_age: float = 90
    operation_poll: float = 10
    start_timeout: float = 240
    stop_timeout: float = 300
    confirm_seconds: float = 30
    cooldown: float = 10
    panel_heartbeat: float = 300

    @classmethod
    def load(cls, env_file: Path = ROOT / ".env") -> Config:
        load_dotenv(env_file, override=False, interpolate=False)

        def required(key: str) -> str:
            value = os.environ.get(key, "").strip()
            if not value or value.startswith("preencha_"):
                raise ValueError(f"Configure {key} no .env.")
            return value

        def number(key: str, default: float, low: float, high: float) -> float:
            value = float(os.environ.get(key, str(default)))
            if not low <= value <= high:
                raise ValueError(f"Valor fora do intervalo permitido: {key}.")
            return value

        def snowflake(key: str) -> int:
            value = required(key)
            if not re.fullmatch(r"[0-9]{15,20}", value) or not 0 < int(value) < 2**64:
                raise ValueError(f"ID Discord invalido: {key}.")
            return int(value)

        url = required("CRAFTY_URL").rstrip("/")
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
        ):
            raise ValueError("CRAFTY_URL deve ser HTTPS loopback, sem caminho ou credenciais.")
        _ = parsed.port
        fingerprint = os.environ.get("CRAFTY_CERT_SHA256", "").replace(":", "").strip()
        if fingerprint and not re.fullmatch(r"[a-fA-F0-9]{64}", fingerprint):
            raise ValueError("CRAFTY_CERT_SHA256 deve conter 64 digitos hexadecimais.")
        ca = os.environ.get("CRAFTY_CA_FILE", "").strip()
        if ca and fingerprint:
            raise ValueError("Escolha CA ou fingerprint, nao ambos.")
        ca_path = str((ROOT / ca).resolve()) if ca else None
        if ca_path and not Path(ca_path).is_file():
            raise ValueError("CRAFTY_CA_FILE nao encontrado.")
        host = os.environ.get("MC_STATUS_HOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("MC_STATUS_HOST deve ser loopback.")
        owner, friend = snowflake("OWNER_DISCORD_ID"), snowflake("FRIEND_DISCORD_ID")
        if owner == friend:
            raise ValueError("Os dois usuarios autorizados devem ser distintos.")
        config = cls(
            discord_token=required("DISCORD_TOKEN"),
            crafty_token=required("CRAFTY_TOKEN"),
            owner_id=owner,
            friend_id=friend,
            guild_id=snowflake("DISCORD_GUILD_ID"),
            channel_id=snowflake("DISCORD_CHANNEL_ID"),
            crafty_url=url,
            server_id=str(UUID(required("CRAFTY_SERVER_ID"))),
            timezone=ZoneInfo(os.environ.get("CRAFTY_TIMEZONE", "America/Sao_Paulo")),
            data_dir=(ROOT / os.environ.get("DATA_DIR", "data")).resolve(),
            log_dir=(ROOT / os.environ.get("LOG_DIR", "logs")).resolve(),
            ca_file=ca_path,
            fingerprint=fingerprint or None,
            crafty_version=os.environ.get("CRAFTY_VERSION", "nao_informada"),
            status_host=host,
            status_port=int(number("MC_STATUS_PORT", 25565, 1, 65535)),
            poll_seconds=number("POLL_SECONDS", 30, 30, 300),
            http_timeout=number("HTTP_TIMEOUT_SECONDS", 10, 2, 30),
            status_timeout=number("STATUS_TIMEOUT_SECONDS", 5, 1, 15),
            stats_max_age=number("STATS_MAX_AGE_SECONDS", 90, 30, 120),
            operation_poll=number("OPERATION_POLL_SECONDS", 10, 5, 30),
            start_timeout=number("START_TIMEOUT_SECONDS", 240, 30, 600),
            stop_timeout=number("STOP_TIMEOUT_SECONDS", 300, 30, 600),
            confirm_seconds=number("CONFIRM_SECONDS", 30, 10, 60),
            cooldown=number("COOLDOWN_SECONDS", 10, 5, 120),
            panel_heartbeat=number("PANEL_HEARTBEAT_SECONDS", 300, 30, 900),
        )
        return config
