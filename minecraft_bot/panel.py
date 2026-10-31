from __future__ import annotations

import asyncio
import time
from datetime import datetime

import discord

from .config import Config
from .models import Snapshot, State
from .storage import Store

TITLE = "Minecraft Survival — Painel de Controle"
UNKNOWN = "Indisponível"
COLORS = {
    State.ONLINE: 0x2ECC71,
    State.OFFLINE: 0xE74C3C,
    State.STARTING: 0xF1C40F,
    State.STOPPING: 0xF1C40F,
    State.UNAVAILABLE: 0x747F8D,
}


def escape(value: str, limit: int = 900) -> str:
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value))[:limit]


def build_embed(
    snapshot: Snapshot, last_success: datetime | None, marker: str, poll_seconds: float = 30
) -> discord.Embed:
    embed = discord.Embed(
        title=TITLE,
        color=COLORS[snapshot.state],
        description=f"**{snapshot.state.value}**\n{escape(snapshot.detail)}",
    )
    count = str(snapshot.online) if snapshot.online is not None else UNKNOWN
    maximum = str(snapshot.maximum) if snapshot.maximum is not None else UNKNOWN
    embed.add_field(name="Jogadores", value=f"{count}/{maximum}" if count != UNKNOWN else UNKNOWN)
    embed.add_field(
        name="Versão Minecraft", value=escape(snapshot.version) if snapshot.version else UNKNOWN
    )
    embed.add_field(name="Software configurado", value="Vanilla")
    names = UNKNOWN
    if snapshot.names is not None:
        names = ", ".join(escape(x, 64) for x in snapshot.names) or "Nenhum"
        if snapshot.online is not None and len(snapshot.names) < snapshot.online:
            names = (names if snapshot.names else UNKNOWN) + " (amostra incompleta)"
    embed.add_field(name="Nicks conectados", value=names[:1024], inline=False)
    uptime = f"Iniciado <t:{int(snapshot.started.timestamp())}:R>" if snapshot.started else UNKNOWN
    embed.add_field(name="Tempo de atividade", value=uptime)
    embed.add_field(
        name="Comunicação com Crafty", value="Conectado" if snapshot.crafty_ok else UNKNOWN
    )
    updated = f"<t:{int(last_success.timestamp())}:F>" if last_success else UNKNOWN
    embed.add_field(name="Última consulta bem-sucedida publicada", value=updated, inline=False)
    embed.set_footer(
        text=f"{marker} • Consulta normal: {poll_seconds:g} s • Parada com servidor vazio"
    )
    return embed


def fingerprint(snapshot: Snapshot, blocked: bool) -> tuple:
    return (
        snapshot.state,
        snapshot.crafty_ok,
        snapshot.detail,
        snapshot.online,
        snapshot.maximum,
        snapshot.names,
        snapshot.version,
        snapshot.started,
        blocked,
    )


class Panel:
    def __init__(self, config: Config, store: Store, client: discord.Client):
        self.config, self.store, self.client = config, store, client
        self.marker = f"crafty-panel:v1:{config.server_id}"
        self.lock = asyncio.Lock()
        self.signature: tuple | None = None
        self.published = 0.0
        self.channel: discord.TextChannel | None = None

    async def _channel(self) -> discord.TextChannel:
        if self.channel is None:
            channel = await self.client.fetch_channel(self.config.channel_id)
            if (
                not isinstance(channel, discord.TextChannel)
                or channel.guild.id != self.config.guild_id
            ):
                raise ValueError("O painel exige um canal de texto da guild configurada.")
            self.channel = channel
        return self.channel

    def _ours(self, message: discord.Message) -> bool:
        return bool(
            self.client.user
            and message.author.id == self.client.user.id
            and message.embeds
            and (message.embeds[0].footer.text or "").startswith(self.marker + " •")
        )

    async def publish(
        self,
        snapshot: Snapshot,
        last_success: datetime | None,
        view: discord.ui.View,
        blocked: bool,
    ) -> bool:
        async with self.lock:
            channel = await self._channel()
            message = None
            panel_id = self.store.value.get("panel_id")
            if panel_id:
                try:
                    message = await channel.fetch_message(panel_id)
                except discord.NotFound:
                    self.store.set(panel_id=None)
                if message and not self._ours(message):
                    raise ValueError("O ID persistido nao pertence a este painel.")
            if message is None:
                async for candidate in channel.history(limit=None, oldest_first=True):
                    if self._ours(candidate):
                        message = candidate
                        break
                if message is not None:
                    self.store.set(panel_id=message.id)
            signature = fingerprint(snapshot, blocked)
            embed = build_embed(snapshot, last_success, self.marker, self.config.poll_seconds)
            if message is None:
                message = await channel.send(
                    embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none()
                )
                self.store.set(panel_id=message.id)
            elif (
                signature != self.signature
                or time.monotonic() - self.published >= self.config.panel_heartbeat
            ):
                await message.edit(
                    embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none()
                )
            else:
                return False
            self.signature, self.published = signature, time.monotonic()
            return True
