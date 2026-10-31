from datetime import UTC, datetime, timedelta

import pytest

from minecraft_bot.crafty import CraftyError
from minecraft_bot.models import State


async def test_online_offline_and_unavailable_are_distinct(harness):
    assert (await harness.monitor.refresh()).state == State.ONLINE
    harness.offline()
    assert (await harness.monitor.refresh()).state == State.OFFLINE
    harness.error = CraftyError("conexao_ou_tls")
    state = await harness.monitor.refresh()
    assert state.state == State.UNAVAILABLE and state.running is None


async def test_reconnect_after_crafty_restart(harness):
    harness.error = CraftyError("conexao_ou_tls")
    await harness.monitor.refresh()
    count = harness.api.stats.await_count
    await harness.monitor.refresh()
    assert harness.api.stats.await_count == count  # Backoff enforced for manual refresh too.
    harness.error = None
    harness.monitor.retry_at = 0
    assert (await harness.monitor.refresh()).state == State.ONLINE


@pytest.mark.parametrize("created", [None, "garbage", "2001-01-01 00:00:00"])
async def test_bad_or_stale_timestamps_fail_closed(harness, created):
    harness.raw["created"] = created
    snapshot = await harness.monitor.refresh()
    assert snapshot.crafty_ok and not snapshot.fresh
    assert snapshot.state == State.UNAVAILABLE


async def test_future_stats_rejected(harness):
    harness.raw["created"] = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
    assert not (await harness.monitor.refresh()).fresh


async def test_port_or_server_mismatch_rejected(harness):
    harness.raw["server_id"]["server_port"] = 25566
    assert not (await harness.monitor.refresh()).crafty_ok


async def test_no_invented_pause_version_or_names(harness):
    harness.live = None
    harness.raw.update(version="", players="unparseable")
    snapshot = await harness.monitor.refresh()
    assert snapshot.version is None and snapshot.names is None
    assert snapshot.state == State.ONLINE  # Empty does NOT imply paused.


async def test_failed_ping_zero_is_not_trusted(harness):
    harness.live = None
    harness.raw.update(int_ping_results="False", online=0)
    assert (await harness.monitor.refresh()).online is None


async def test_external_waiting_start(harness):
    harness.offline()
    harness.raw["waiting_start"] = True
    assert (await harness.monitor.refresh()).state == State.STARTING


async def test_crafty_411_started_is_utc_but_created_is_local(harness):
    local_now = datetime.now(harness.config.timezone).replace(tzinfo=None)
    harness.raw["created"] = local_now.isoformat()
    snapshot = await harness.monitor.refresh()
    assert snapshot.fresh
    assert snapshot.started == datetime(2026, 1, 1, 12, tzinfo=UTC)
