from __future__ import annotations

import asyncio
import logging

import discord

from .config import Config
from .discord_ui import ControlView
from .models import State
from .monitor import Monitor
from .operations import Operations
from .panel import Panel
from .security import Cooldown
from .storage import Store

log = logging.getLogger(__name__)


class MinecraftBot(discord.Client):
    def __init__(self, config: Config, monitor: Monitor, operations: Operations, store: Store):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(
            intents=intents, max_messages=None, allowed_mentions=discord.AllowedMentions.none()
        )
        self.config, self.monitor, self.operations, self.store = config, monitor, operations, store
        self.cooldown = Cooldown(config.cooldown)
        self.panel = Panel(config, store, self)
        self.worker: asyncio.Task | None = None
        self.interactions: set[asyncio.Task] = set()
        self.operations.changed = self.publish

    async def setup_hook(self) -> None:
        self.add_view(ControlView(self))
        self.worker = asyncio.create_task(self._monitor_loop(), name="minecraft-monitor")

    async def on_ready(self) -> None:
        log.info("discord_ready")

    async def on_error(self, event_method: str, *args: object, **kwargs: object) -> None:
        log.error("discord_event_failed event=%s", event_method)

    async def publish(self) -> None:
        if not self.is_ready() or self.is_closed():
            return
        snapshot = self.monitor.snapshot
        blocked = (
            not snapshot.crafty_ok
            or (not snapshot.fresh and snapshot.state != State.OFFLINE)
            or snapshot.state in {
                State.UNAVAILABLE,
                State.STARTING,
                State.STOPPING,
            }
            or bool(self.store.value.get("pending"))
        )
        try:
            await self.panel.publish(
                snapshot, self.monitor.last_success, ControlView(self, blocked=blocked, state=snapshot.state), blocked
            )
        except discord.NotFound:
            self.panel.channel = None
            log.warning("panel_channel_or_message_missing")
        except discord.Forbidden:
            log.warning("panel_permission_denied")
        except discord.HTTPException:
            log.warning("panel_http_failure")
        except ValueError:
            log.error("panel_identity_or_channel_invalid")

    async def _monitor_loop(self) -> None:
        while not self.is_closed():
            await self.wait_until_ready()
            if not self.operations.lock.locked():
                await self.monitor.refresh()
                await self.publish()
            await asyncio.sleep(self.config.poll_seconds)

    async def close(self) -> None:
        tasks = [
            task
            for task in [self.worker, *self.interactions]
            if task and task is not asyncio.current_task()
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await super().close()
