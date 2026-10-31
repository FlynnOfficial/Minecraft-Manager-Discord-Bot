from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from minecraft_bot.config import Config
from minecraft_bot.models import LiveStatus
from minecraft_bot.monitor import Monitor
from minecraft_bot.operations import Operations
from minecraft_bot.storage import Store


@pytest.fixture
def config(tmp_path):
    return Config(
        discord_token="discord-secret",
        crafty_token="crafty-secret",
        owner_id=111111111111111111,
        friend_id=222222222222222222,
        guild_id=333333333333333333,
        channel_id=444444444444444444,
        crafty_url="https://127.0.0.1:8443",
        server_id="12345678-1234-1234-1234-123456789abc",
        timezone=ZoneInfo("America/Sao_Paulo"),
        data_dir=tmp_path / "data",
        log_dir=tmp_path / "logs",
        operation_poll=0.001,
        start_timeout=0.03,
        stop_timeout=0.03,
    )


@pytest.fixture
def store(config):
    return Store(config.data_dir, {"server": config.server_id})


def stats(config, running=True, count=0):
    return {
        "server_id": {
            "server_id": config.server_id,
            "server_port": 25565,
            "type": "minecraft-java",
            "stop_command": "stop",
        },
        "running": running,
        "created": datetime.now(UTC).isoformat(),
        "online": count,
        "max": 2,
        "players": "[]",
        "version": "1.21.3",
        "int_ping_results": "True" if running else "False",
        "waiting_start": False,
        "started": "2026-01-01 12:00:00" if running else "",
    }


class Harness:
    def __init__(self, config, store):
        self.config, self.store = config, store
        self.raw = stats(config)
        self.live = LiveStatus(0, 2, (), "1.21.3")
        self.error = None
        self.apply_action = True
        self.api = AsyncMock()
        self.api.stats.side_effect = self.get_stats
        self.api.action.side_effect = self.action
        self.probe = AsyncMock()
        self.probe.read.side_effect = self.get_live
        self.monitor = Monitor(config, self.api, self.probe, store)
        self.ops = Operations(config, self.api, self.monitor, store)

    async def get_stats(self):
        if self.error:
            raise self.error
        return dict(self.raw)

    async def get_live(self):
        return self.live

    def offline(self):
        self.raw = stats(self.config, False)
        self.live = None

    def players(self, number):
        self.raw = stats(self.config, True, number)
        self.live = replace(self.live, online=number)

    async def action(self, action):
        if self.apply_action:
            self.raw = stats(self.config, action == "start_server")
            self.live = LiveStatus(0, 2, (), "1.21.3") if action == "start_server" else None


@pytest.fixture
def harness(config, store):
    return Harness(config, store)
