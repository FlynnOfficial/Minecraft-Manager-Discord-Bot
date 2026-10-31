import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from minecraft_bot.discord_ui import permission
from minecraft_bot.logging_setup import SafeFormatter
from minecraft_bot.security import Cooldown, authorized


def test_exact_two_ids(config):
    for user in (config.owner_id, config.friend_id):
        assert authorized(config, user, config.guild_id, config.channel_id)
    assert not authorized(config, 999, config.guild_id, config.channel_id)
    assert not authorized(config, config.owner_id, None, config.channel_id)
    assert not authorized(config, config.owner_id, config.guild_id, 999)


async def test_discord_admin_has_no_bypass(config):
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=999, guild_permissions=SimpleNamespace(administrator=True)),
        guild_id=config.guild_id,
        channel_id=config.channel_id,
        response=SimpleNamespace(is_done=lambda: False, send_message=AsyncMock()),
    )
    assert not await permission(SimpleNamespace(config=config), interaction)
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


def test_cooldown_per_user():
    cooldown = Cooldown(10)
    assert cooldown.accept(1)
    assert not cooldown.accept(1)
    assert cooldown.accept(2)


@pytest.mark.parametrize(
    "template,args",
    [
        ("token=%s", ("super-secret",)),
        ("Authorization: Bearer other-secret", ()),
        ("https://host/path?token=super-secret", ()),
    ],
)
def test_no_secrets_in_logs(template, args):
    formatter = SafeFormatter(("super-secret",))
    record = logging.LogRecord("test", logging.ERROR, "", 0, template, args, None)
    output = formatter.format(record)
    assert "super-secret" not in output
    assert "other-secret" not in output
    assert "[REDACTED]" in output


def test_exception_body_not_logged():
    error = ValueError("secret-in-http-exception")
    record = logging.LogRecord(
        "test", logging.ERROR, "", 0, "failed", (), (ValueError, error, None)
    )
    assert "secret-in-http-exception" not in SafeFormatter(()).format(record)
