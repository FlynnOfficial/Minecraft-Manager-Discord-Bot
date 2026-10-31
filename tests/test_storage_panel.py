from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from minecraft_bot.models import Snapshot, State
from minecraft_bot.panel import Panel, build_embed
from minecraft_bot.storage import InstanceLock, Store


def test_state_persists(config, store):
    store.set(panel_id=123456, pending={"action": "stop_server", "sent_at": 123.0})
    restored = Store(config.data_dir, {"server": config.server_id})
    assert restored.value == store.value
    assert not store.path.with_suffix(".tmp").exists()


def test_corrupt_state_fails_closed(config, store):
    store.path.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError):
        Store(config.data_dir, {"server": config.server_id})


def test_changed_server_scope_rejected(config, store):
    store.set(panel_id=123)
    with pytest.raises(ValueError):
        Store(config.data_dir, {"server": "different"})


def test_only_one_instance(config):
    with InstanceLock(config.data_dir):
        with pytest.raises(RuntimeError):
            with InstanceLock(config.data_dir):
                pass
    with InstanceLock(config.data_dir):
        pass


def test_embed_unknown_and_escape():
    embed = build_embed(Snapshot(names=("@everyone",)), None, "test")
    fields = {field.name: field.value for field in embed.fields}
    assert fields["Versão Minecraft"] == "Indisponível"
    assert "@everyone" not in fields["Nicks conectados"]
    assert embed.color.value == 0x747F8D


class Channel:
    def __init__(self):
        self.messages = []
        self.send = AsyncMock(side_effect=self._send)
        self.fetch_message = AsyncMock(side_effect=self._fetch)

    async def _send(self, **kwargs):
        message = SimpleNamespace(
            id=1234, author=SimpleNamespace(id=42), embeds=[kwargs["embed"]], edit=AsyncMock()
        )
        self.messages.append(message)
        return message

    async def _fetch(self, message_id):
        for message in self.messages:
            if message.id == message_id:
                return message
        raise discord.NotFound(SimpleNamespace(status=404, reason="Not Found"), "deleted")

    async def history(self, **kwargs):
        for message in self.messages:
            yield message


@pytest.fixture
def panel(config, store):
    result = Panel(config, store, SimpleNamespace(user=SimpleNamespace(id=42)))
    result.channel = Channel()
    return result


async def test_one_panel_no_unnecessary_edits(panel, store):
    snapshot = Snapshot(state=State.ONLINE, crafty_ok=True, online=0)
    view = discord.ui.View(timeout=None)
    assert await panel.publish(snapshot, datetime.now(UTC), view, False)
    assert not await panel.publish(snapshot, datetime.now(UTC), view, False)
    assert panel.channel.send.await_count == 1
    assert store.value["panel_id"] == 1234
    panel.channel.messages[0].edit.assert_not_awaited()
    changed = Snapshot(state=State.ONLINE, crafty_ok=True, online=1)
    assert await panel.publish(changed, datetime.now(UTC), view, False)
    panel.channel.messages[0].edit.assert_awaited_once()


async def test_panel_recovers_after_restart(panel, config, store):
    await panel.publish(Snapshot(), None, discord.ui.View(), True)
    restored = Panel(config, Store(config.data_dir, {"server": config.server_id}), panel.client)
    restored.channel = panel.channel
    await restored.publish(Snapshot(), None, discord.ui.View(), True)
    assert panel.channel.send.await_count == 1


async def test_deleted_panel_recreated(panel):
    await panel.publish(Snapshot(), None, discord.ui.View(), True)
    panel.channel.messages.clear()
    await panel.publish(Snapshot(), None, discord.ui.View(), True)
    assert panel.channel.send.await_count == 2


async def test_lost_send_response_recovers_by_marker(panel, store):
    await panel.publish(Snapshot(), None, discord.ui.View(), True)
    store.set(panel_id=None)  # Simulate crash between remote send and local persistence.
    panel.signature = None
    await panel.publish(Snapshot(), None, discord.ui.View(), True)
    assert panel.channel.send.await_count == 1
    assert store.value["panel_id"] == 1234


async def test_forbidden_history_does_not_create_duplicate(panel):
    async def denied(**kwargs):
        raise discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "denied")
        yield  # Async generator contract.

    panel.channel.history = denied
    with pytest.raises(discord.Forbidden):
        await panel.publish(Snapshot(), None, discord.ui.View(), True)
    panel.channel.send.assert_not_awaited()
