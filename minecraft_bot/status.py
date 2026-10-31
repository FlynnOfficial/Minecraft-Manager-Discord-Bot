from __future__ import annotations

import asyncio

from mcstatus import JavaServer

from .config import Config
from .models import LiveStatus, integer


class StatusProbe:
    def __init__(self, config: Config):
        self.timeout = config.status_timeout
        self.server = JavaServer(config.status_host, config.status_port, timeout=self.timeout)

    async def read(self) -> LiveStatus | None:
        try:
            async with asyncio.timeout(self.timeout):
                result = await self.server.async_status(tries=1)
            raw = result.raw
            players = raw.get("players", {})
            online, maximum = integer(players.get("online")), integer(players.get("max"))
            sample = players.get("sample")
            names = None
            if isinstance(sample, list) and all(
                isinstance(p, dict) and isinstance(p.get("name"), str) for p in sample
            ):
                names = tuple(p["name"][:64] for p in sample[:100])
            if online == 0:
                names = ()
            version = raw.get("version", {}).get("name")
            return LiveStatus(online, maximum, names, version if isinstance(version, str) else None)
        except (OSError, TimeoutError, ValueError, KeyError, TypeError, AttributeError):
            return None
