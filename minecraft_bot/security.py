from __future__ import annotations

import time

from .config import Config


def authorized(config: Config, user_id: int, guild_id: int | None, channel_id: int | None) -> bool:
    return (
        user_id in {config.owner_id, config.friend_id}
        and guild_id == config.guild_id
        and channel_id == config.channel_id
    )


class Cooldown:
    def __init__(self, seconds: float):
        self.seconds = seconds
        self.last: dict[int, float] = {}

    def accept(self, user_id: int) -> bool:
        now = time.monotonic()
        if now - self.last.get(user_id, -float("inf")) < self.seconds:
            return False
        self.last[user_id] = now
        return True
