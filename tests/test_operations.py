import asyncio
import time
from dataclasses import replace

import pytest

from minecraft_bot.crafty import CraftyError
from minecraft_bot.models import State
from minecraft_bot.monitor import Monitor
from minecraft_bot.operations import Operations, Rejected
from minecraft_bot.storage import Store


async def test_start_offline(harness):
    harness.offline()
    assert "confirmada" in await harness.ops.start(1)
    harness.api.action.assert_awaited_once_with("start_server")
    assert harness.store.value["pending"] is None


async def test_start_already_online(harness):
    assert "já está" in await harness.ops.start(1)
    harness.api.action.assert_not_awaited()


@pytest.mark.parametrize("count", [1, 2])
async def test_stop_with_players(harness, count):
    harness.players(count)
    with pytest.raises(Rejected, match="jogadores"):
        await harness.ops.prepare_stop(1)
    harness.api.action.assert_not_awaited()


@pytest.mark.parametrize("unknown", [None, "missing_count"])
async def test_stop_unknown_count(harness, unknown):
    harness.live = None if unknown is None else replace(harness.live, online=None)
    with pytest.raises(Rejected):
        await harness.ops.prepare_stop(1)
    harness.api.action.assert_not_awaited()


async def test_player_joins_during_confirmation(harness):
    ticket = await harness.ops.prepare_stop(1)
    harness.players(1)
    with pytest.raises(Rejected, match="jogadores"):
        await harness.ops.confirm_stop(ticket, 1)
    harness.api.action.assert_not_awaited()


async def test_stop_empty_requires_confirmation_and_rechecks(harness):
    ticket = await harness.ops.prepare_stop(1)
    harness.api.action.assert_not_awaited()
    assert "confirmado" in await harness.ops.confirm_stop(ticket, 1)
    assert harness.api.stats.await_count >= 3
    harness.api.action.assert_awaited_once_with("stop_server")
    with pytest.raises(Rejected):
        await harness.ops.confirm_stop(ticket, 1)


async def test_missing_or_unsafe_crafty_stop_command_blocks_shutdown(harness):
    harness.raw["server_id"]["stop_command"] = ""
    with pytest.raises(Rejected, match="Stop Command"):
        await harness.ops.prepare_stop(1)
    harness.api.action.assert_not_awaited()


async def test_foreign_and_expired_confirmation(harness):
    ticket = await harness.ops.prepare_stop(1)
    with pytest.raises(Rejected):
        await harness.ops.confirm_stop(ticket, 2)
    expired = replace(ticket, expires=time.monotonic() - 1)
    harness.ops.ticket = expired
    with pytest.raises(Rejected):
        await harness.ops.confirm_stop(expired, 1)
    harness.api.action.assert_not_awaited()


async def test_confirm_reservation_blocks_start(harness):
    ticket = await harness.ops.prepare_stop(1)
    with pytest.raises(Rejected, match="confirmação"):
        await harness.ops.start(2)
    harness.ops.cancel(ticket, 1)
    assert "já está" in await harness.ops.start(2)


async def test_concurrent_start_exactly_once(harness):
    harness.offline()
    entered, release = asyncio.Event(), asyncio.Event()
    original = harness.api.action.side_effect

    async def slow_action(action):
        entered.set()
        await release.wait()
        await original(action)

    harness.api.action.side_effect = slow_action
    first = asyncio.create_task(harness.ops.start(1))
    await entered.wait()
    with pytest.raises(Rejected, match="andamento"):
        await harness.ops.start(2)
    with pytest.raises(Rejected, match="andamento"):
        await harness.ops.prepare_stop(2)
    release.set()
    await first
    assert harness.api.action.await_count == 1


@pytest.mark.parametrize("code", ["conexao_ou_tls", "autenticacao_ou_permissao"])
async def test_api_failure_blocks_all_actions(harness, code):
    harness.error = CraftyError(code)
    with pytest.raises(Rejected, match="indisponível"):
        await harness.ops.start(1)
    harness.api.action.assert_not_awaited()
    assert harness.monitor.snapshot.state == State.UNAVAILABLE


async def test_response_lost_observe_without_resending(harness):
    harness.offline()
    original = harness.api.action.side_effect

    async def lost_reply(action):
        await original(action)
        raise CraftyError("conexao_ou_tls", uncertain=True)

    harness.api.action.side_effect = lost_reply
    assert "confirmada" in await harness.ops.start(1)
    assert harness.api.action.await_count == 1


async def test_timeout_keeps_journal_and_blocks_retries(harness):
    harness.offline()
    harness.apply_action = False
    assert "não foi confirmado" in await harness.ops.start(1)
    assert harness.store.value["pending"]["action"] == "start_server"
    with pytest.raises(Rejected):
        await harness.ops.start(2)
    assert harness.api.action.await_count == 1


async def test_restart_during_operation_never_resends(harness):
    harness.offline()
    harness.store.set(pending={"action": "start_server", "sent_at": time.time() - 10})
    restored = Store(harness.config.data_dir, {"server": harness.config.server_id})
    monitor = Monitor(harness.config, harness.api, harness.probe, restored)
    ops = Operations(harness.config, harness.api, monitor, restored)
    with pytest.raises(Rejected):
        await ops.start(1)
    await harness.action("start_server")
    await monitor.refresh()
    assert restored.value["pending"] is None
    harness.api.action.assert_not_awaited()


async def test_old_stats_cannot_confirm_operation(harness):
    harness.store.set(pending={"action": "start_server", "sent_at": time.time() + 1})
    await harness.monitor.refresh()
    assert harness.store.value["pending"] is not None


async def test_cancelled_task_preserves_journal(harness):
    harness.offline()
    entered = asyncio.Event()

    async def never_returns(action):
        entered.set()
        await asyncio.Event().wait()

    harness.api.action.side_effect = never_returns
    task = asyncio.create_task(harness.ops.start(1))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert harness.store.value["pending"] is not None
    assert not harness.ops.lock.locked()
