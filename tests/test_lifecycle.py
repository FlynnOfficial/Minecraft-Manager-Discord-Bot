import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from minecraft_bot import __main__ as entry
from minecraft_bot.bot import MinecraftBot


async def test_discord_disconnected_does_not_publish_or_start(config, harness, store):
    bot = MinecraftBot(config, harness.monitor, harness.ops, store)
    bot.is_ready = MagicMock(return_value=False)
    bot.panel.publish = AsyncMock()
    await bot.publish()
    bot.panel.publish.assert_not_awaited()
    harness.api.action.assert_not_awaited()
    await bot.close()


async def test_deleted_channel_and_missing_permission_keep_bot_alive(config, harness, store):
    bot = MinecraftBot(config, harness.monitor, harness.ops, store)
    bot.is_ready = MagicMock(return_value=True)
    bot.panel.channel = object()
    bot.panel.publish = AsyncMock(
        side_effect=discord.NotFound(
            SimpleNamespace(status=404, reason="Not Found"), "missing channel"
        )
    )
    await bot.publish()
    assert bot.panel.channel is None
    bot.panel.publish.side_effect = discord.Forbidden(
        SimpleNamespace(status=403, reason="Forbidden"), "missing permissions"
    )
    await bot.publish()
    assert not bot.is_closed()
    harness.api.action.assert_not_awaited()
    await bot.close()


async def test_stop_file_closes_bot_without_minecraft_action(config, monkeypatch):
    api = AsyncMock()
    api_context = AsyncMock()
    api_context.__aenter__.return_value = api
    monkeypatch.setattr(entry, "CraftyClient", lambda _: api_context)
    monkeypatch.setattr(entry.signal, "signal", lambda *args: None)
    started = asyncio.Event()
    closed = asyncio.Event()

    class FakeBot:
        worker = None

        def __init__(self, *args):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.set()

        async def start(self, *args, **kwargs):
            started.set()
            await closed.wait()

        async def close(self):
            closed.set()

    monkeypatch.setattr(entry, "MinecraftBot", FakeBot)
    task = asyncio.create_task(entry.run(config))
    await started.wait()
    (config.data_dir / "stop.request").touch()
    await asyncio.wait_for(task, timeout=5)
    assert closed.is_set()
    api.action.assert_not_awaited()
