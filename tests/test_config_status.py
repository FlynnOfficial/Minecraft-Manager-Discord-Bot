from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from minecraft_bot.config import Config
from minecraft_bot.status import StatusProbe


@pytest.fixture
def env(monkeypatch, tmp_path):
    values = {
        "DISCORD_TOKEN": "valid-test-token",
        "CRAFTY_TOKEN": "valid-test-token",
        "OWNER_DISCORD_ID": "111111111111111111",
        "FRIEND_DISCORD_ID": "222222222222222222",
        "DISCORD_GUILD_ID": "333333333333333333",
        "DISCORD_CHANNEL_ID": "444444444444444444",
        "CRAFTY_URL": "https://127.0.0.1:8443",
        "CRAFTY_SERVER_ID": "12345678-1234-1234-1234-123456789abc",
        "DATA_DIR": str(tmp_path / "data"),
        "LOG_DIR": str(tmp_path / "logs"),
        "CRAFTY_CA_FILE": "",
        "CRAFTY_CERT_SHA256": "",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return tmp_path / "absent.env"


@pytest.mark.parametrize(
    "key,value",
    [
        ("CRAFTY_URL", "http://127.0.0.1:8443"),
        ("CRAFTY_URL", "https://remote.example:8443"),
        ("CRAFTY_URL", "https://token@localhost:8443"),
        ("CRAFTY_URL", "https://localhost:8443/api/v2"),
        ("FRIEND_DISCORD_ID", "111111111111111111"),
        ("OWNER_DISCORD_ID", "admin"),
        ("CRAFTY_CERT_SHA256", "00"),
        ("MC_STATUS_HOST", "public.example"),
        ("POLL_SECONDS", "1"),
    ],
)
def test_unsafe_configuration_rejected(env, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        Config.load(env)


def test_config_repr_hides_tokens(env):
    assert "valid-test-token" not in repr(Config.load(env))


async def test_live_sample_can_be_incomplete(config):
    probe = StatusProbe(config)
    probe.server = SimpleNamespace(
        async_status=AsyncMock(
            return_value=SimpleNamespace(
                raw={
                    "players": {"online": 2, "max": 2, "sample": [{"name": "Steve"}]},
                    "version": {"name": "1.21.3"},
                }
            )
        )
    )
    status = await probe.read()
    assert status.online == 2 and status.names == ("Steve",)


async def test_live_probe_failure_means_unknown_not_zero(config):
    probe = StatusProbe(config)
    probe.server = SimpleNamespace(async_status=AsyncMock(side_effect=TimeoutError))
    assert await probe.read() is None
