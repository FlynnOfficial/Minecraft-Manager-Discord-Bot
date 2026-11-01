from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import uuid4

from .config import Config
from .crafty import CraftyClient, CraftyError
from .logging_setup import audit
from .models import Snapshot, State
from .monitor import Monitor
from .storage import Store


class Rejected(Exception):
    pass


@dataclass(frozen=True)
class Ticket:
    token: str
    user_id: int
    expires: float


class Operations:
    def __init__(self, config: Config, api: CraftyClient, monitor: Monitor, store: Store):
        self.config, self.api, self.monitor, self.store = config, api, monitor, store
        self.lock = asyncio.Lock()
        self.ticket: Ticket | None = None
        self.changed: Callable[[], Awaitable[None]] | None = None

    def _check(self, *, confirming: bool = False) -> None:
        if self.lock.locked():
            raise Rejected("Já existe uma operação em andamento.")
        if self.store.value.get("pending"):
            raise Rejected(
                "Existe uma operação sem resultado confirmado. Aguarde ou consulte os logs."
            )
        if self.ticket and self.ticket.expires <= time.monotonic():
            self.ticket = None
        if self.ticket and not confirming:
            raise Rejected("Existe uma confirmação de desligamento pendente.")

    @staticmethod
    def _known(snapshot: Snapshot) -> None:
        if not snapshot.crafty_ok:
            raise Rejected("Crafty indisponível. Nenhuma ação foi enviada.")
        if snapshot.running is None or (
            not snapshot.fresh and snapshot.state != State.OFFLINE
        ):
            raise Rejected("Não há estado recente e confiável do Minecraft.")
        if snapshot.waiting or snapshot.state in {State.STARTING, State.STOPPING}:
            raise Rejected("O servidor já está em transição. Aguarde.")
        if snapshot.state == State.UNAVAILABLE:
            raise Rejected("Estado do servidor inconclusivo; ação bloqueada por segurança.")

    @classmethod
    def _empty(cls, snapshot: Snapshot) -> None:
        cls._known(snapshot)
        if snapshot.running is False:
            raise Rejected("O Minecraft já está desligado.")
        if not snapshot.graceful_stop:
            raise Rejected("Parada bloqueada: confira no Crafty se Stop Command é exatamente stop.")
        if snapshot.online is not None and snapshot.online > 0:
            raise Rejected("Desligamento recusado: há jogadores conectados.")
        if snapshot.api_online is not None and snapshot.api_online > 0:
            raise Rejected("O Crafty ainda informa jogadores. Aguarde a próxima coleta.")
        if snapshot.live is None or snapshot.live.online != 0:
            raise Rejected("Não foi possível confirmar zero jogadores por consulta local.")

    async def start(self, user_id: int) -> str:
        self._check()
        async with self.lock:
            snapshot = await self.monitor.refresh()
            self._known(snapshot)
            if snapshot.running:
                audit("start", user_id, "already_running")
                return "O Minecraft já está em execução. Nenhuma ação foi necessária."
            return await self._execute("start_server", user_id)

    async def prepare_stop(self, user_id: int) -> Ticket:
        self._check()
        async with self.lock:
            self._empty(await self.monitor.refresh())
            self.ticket = Ticket(
                uuid4().hex, user_id, time.monotonic() + self.config.confirm_seconds
            )
            audit("stop_confirmation", user_id, "issued")
            return self.ticket

    def cancel(self, ticket: Ticket, user_id: int) -> None:
        if self.ticket == ticket and ticket.user_id == user_id:
            self.ticket = None
            audit("stop_confirmation", user_id, "cancelled_or_expired")

    async def confirm_stop(self, ticket: Ticket, user_id: int) -> str:
        self._check(confirming=True)
        async with self.lock:
            if (
                self.ticket != ticket
                or ticket.user_id != user_id
                or ticket.expires <= time.monotonic()
            ):
                raise Rejected("Confirmação expirada ou inválida. Clique em Desligar novamente.")
            self.ticket = None  # Single use, even if the recheck fails.
            self._empty(await self.monitor.refresh())
            return await self._execute("stop_server", user_id)

    async def _notify(self) -> None:
        if self.changed:
            await self.changed()

    async def _execute(self, action: str, user_id: int) -> str:
        self.store.set(pending={"action": action, "sent_at": time.time(), "user_id": user_id})
        audit(action, user_id, "sending")
        try:
            await self.api.action(action)
        except CraftyError as error:
            audit(action, user_id, error.code)
            if not error.uncertain:
                self.store.set(pending=None)
                await self.monitor.refresh()
                await self._notify()
                raise Rejected(
                    "O Crafty recusou a ação. Confira token, permissões e logs."
                ) from None
        self.monitor.snapshot = self.monitor._reconcile(self.monitor.snapshot)
        await self._notify()
        timeout = (
            self.config.start_timeout if action == "start_server" else self.config.stop_timeout
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            await self.monitor.refresh()
            await self._notify()
            if not self.store.value.get("pending"):
                audit(action, user_id, "confirmed")
                return (
                    "Inicialização confirmada: Minecraft respondeu ao status local."
                    if action == "start_server"
                    else "Desligamento confirmado pelo Crafty."
                )
            await asyncio.sleep(
                min(self.config.operation_poll, max(0, deadline - time.monotonic()))
            )
        self.monitor.snapshot = self.monitor._reconcile(self.monitor.snapshot)
        await self._notify()
        audit(action, user_id, "unconfirmed_timeout")
        return (
            "O resultado ainda não foi confirmado. O bot continuará monitorando, sem repetir "
            "o comando. Os controles ficam bloqueados até reconciliação; consulte o README."
        )
