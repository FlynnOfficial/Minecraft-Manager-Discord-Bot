from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import TYPE_CHECKING

import discord

from .logging_setup import audit
from .operations import Rejected, Ticket
from .security import authorized

if TYPE_CHECKING:
    from .bot import MinecraftBot

log = logging.getLogger(__name__)


async def reply(interaction: discord.Interaction, content: str, **kwargs: object) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(content, ephemeral=True, **kwargs)
    else:
        await interaction.response.send_message(content, ephemeral=True, **kwargs)


async def permission(bot: MinecraftBot, interaction: discord.Interaction) -> bool:
    if not authorized(
        bot.config, interaction.user.id, interaction.guild_id, interaction.channel_id
    ):
        audit("interaction_denied", interaction.user.id, "wrong_user_or_location")
        await reply(interaction, "Você não possui permissão para usar estes controles.")
        return False
    return True


async def execute(
    bot: MinecraftBot, interaction: discord.Interaction, work: Awaitable[str]
) -> None:
    task = asyncio.current_task()
    bot.interactions.add(task)
    try:
        result = await work
        await reply(interaction, result)
    except Rejected as error:
        audit("operation_rejected", interaction.user.id, str(error))
        await reply(interaction, str(error))
    except discord.HTTPException:
        log.warning("interaction_response_failed")
    except Exception as error:
        log.error("interaction_failed type=%s", type(error).__name__)
        await reply(interaction, "Falha interna. Consulte os logs; nenhum comando será repetido.")
    finally:
        bot.interactions.discard(task)
        await bot.publish()


class ConfirmView(discord.ui.View):
    def __init__(self, bot: MinecraftBot, ticket: Ticket):
        super().__init__(timeout=bot.config.confirm_seconds)
        self.bot, self.ticket = bot, ticket

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await permission(self.bot, interaction):
            return False
        if interaction.user.id != self.ticket.user_id:
            await reply(interaction, "Esta confirmação pertence a outro usuário.")
            return False
        return True

    @discord.ui.button(label="Confirmar desligamento", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        self.stop()
        await execute(
            self.bot,
            interaction,
            self.bot.operations.confirm_stop(self.ticket, interaction.user.id),
        )

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.bot.operations.cancel(self.ticket, interaction.user.id)
        self.stop()
        await interaction.response.edit_message(content="Desligamento cancelado.", view=None)

    async def on_timeout(self) -> None:
        self.bot.operations.cancel(self.ticket, self.ticket.user_id)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        log.error("confirmation_failed type=%s", type(error).__name__)
        await reply(interaction, "Falha na confirmação. Consulte os logs.")


class ControlView(discord.ui.View):
    def __init__(self, bot: MinecraftBot, *, blocked: bool = False):
        super().__init__(timeout=None)
        self.bot = bot
        self.start_button.disabled = blocked
        self.stop_button.disabled = blocked

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await permission(self.bot, interaction):
            return False
        if interaction.message is None or interaction.message.id != self.bot.store.value.get(
            "panel_id"
        ):
            await reply(interaction, "Este painel não está ativo. Use a mensagem atual do canal.")
            return False
        if not self.bot.cooldown.accept(interaction.user.id):
            await reply(interaction, "Aguarde alguns segundos antes de usar outro controle.")
            return False
        return True

    @discord.ui.button(
        label="Ligar",
        emoji="▶️",
        style=discord.ButtonStyle.success,
        custom_id="minecraft:power:on:v1",
    )
    async def start_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await execute(self.bot, interaction, self.bot.operations.start(interaction.user.id))

    @discord.ui.button(
        label="Desligar",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="minecraft:power:off:v1",
    )
    async def stop_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            ticket = await self.bot.operations.prepare_stop(interaction.user.id)
            view = ConfirmView(self.bot, ticket)
            await reply(
                interaction,
                "O servidor está vazio na consulta atual. Confirmar a parada? "
                "O bot verificará novamente. Não entre no Minecraft durante a operação.",
                view=view,
            )
        except Rejected as error:
            audit("stop_rejected", interaction.user.id, str(error))
            await reply(interaction, str(error))

    @discord.ui.button(
        label="Atualizar",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="minecraft:refresh:v1",
    )
    async def refresh_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        async def refresh() -> str:
            snapshot = await self.bot.monitor.refresh()
            await self.bot.publish()
            audit("refresh", interaction.user.id, "ok" if snapshot.crafty_ok else "unavailable")
            return (
                "Consulta concluída; painel atualizado se houve alteração."
                if snapshot.crafty_ok
                else "Crafty indisponível; reconexão automática com intervalo controlado."
            )

        await execute(self.bot, interaction, refresh())

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        log.error("control_failed type=%s", type(error).__name__)
        await reply(interaction, "Falha interna. Consulte os logs.")
