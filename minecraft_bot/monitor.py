from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import replace
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .config import Config
from .crafty import CraftyClient, CraftyError
from .models import Snapshot, State, integer, timestamp
from .status import StatusProbe
from .storage import Store

log = logging.getLogger(__name__)


class Monitor:
    def __init__(self, config: Config, api: CraftyClient, probe: StatusProbe, store: Store):
        self.config, self.api, self.probe, self.store = config, api, probe, store
        self.snapshot = Snapshot()
        self.lock = asyncio.Lock()
        self.failures = 0
        self.retry_at = 0.0
        self.last_success: datetime | None = None

    async def refresh(self) -> Snapshot:
        async with self.lock:
            if time.monotonic() < self.retry_at:
                return self.snapshot
            try:
                raw = await self.api.stats()
                result = await self._parse(raw)
                self.failures, self.retry_at = 0, 0.0
                self.last_success = result.observed
            except CraftyError as error:
                self.failures = min(self.failures + 1, 5)
                self.retry_at = time.monotonic() + min(30 * 2 ** (self.failures - 1), 300)
                result = Snapshot(detail=f"Crafty indisponível ({error.code})")
                if self.snapshot.crafty_ok or self.failures == 1:
                    log.warning("crafty_unavailable code=%s", error.code)
            self.snapshot = self._reconcile(result)
            return self.snapshot

    async def _parse(self, raw: dict) -> Snapshot:
        now = datetime.now(UTC)
        server = raw.get("server_id")
        if not isinstance(server, dict) or str(server.get("server_id")) != self.config.server_id:
            raise CraftyError("identidade_do_servidor_incompativel")
        if server.get("type") != "minecraft-java":
            raise CraftyError("servidor_nao_e_minecraft_java")
        if server.get("server_port") != self.config.status_port:
            raise CraftyError("porta_status_diverge_do_crafty")
        collected = timestamp(raw.get("created"), self.config.timezone)
        fresh = collected is not None and -5 <= (now - collected).total_seconds() <= (
            self.config.stats_max_age
        )
        running = raw["running"]
        live = await self.probe.read()
        maintenance = raw.get("updating") is True or raw.get("importing") is True
        waiting = raw.get("waiting_start") is True or maintenance
        ping_ok = raw.get("int_ping_results") in (True, "True")
        api_online = integer(raw.get("online")) if fresh and ping_ok else None
        count = live.online if live else api_online
        maximum = live.maximum if live else integer(raw.get("max")) if fresh and ping_ok else None
        names = live.names if live else None
        if names is None and fresh and ping_ok:
            try:
                players = raw.get("players")
                if isinstance(players, str):
                    players = json.loads(players)
                if isinstance(players, list) and all(isinstance(p, str) for p in players):
                    names = tuple(p[:64] for p in players[:100])
            except (ValueError, TypeError):
                pass
        version = live.version if live else raw.get("version") if fresh and ping_ok else None
        if not isinstance(version, str) or not version.strip():
            version = None
        started = timestamp(raw.get("started"), ZoneInfo("UTC")) if running else None
        if started and started > now:
            started = None
        state = State.ONLINE if running else State.OFFLINE
        detail = "Conectado"
        if waiting:
            state = State.STARTING
        if maintenance:
            state, detail = State.UNAVAILABLE, "Conectado; manutenção em andamento no Crafty"
        elif not fresh and running:
            state, detail = (
                State.UNAVAILABLE,
                "Conectado; estatísticas antigas ou sem data confiável",
            )
        elif live and not running:
            state, detail = State.UNAVAILABLE, "Conectado; processo e status divergem"
        elif running and not live and not ping_ok:
            state, detail = State.UNAVAILABLE, "Conectado; processo ativo, prontidão não confirmada"
        if not running and not live and not waiting:
            count, names = 0, ()
        return Snapshot(
            state=state,
            crafty_ok=True,
            detail=detail,
            running=running,
            online=count,
            maximum=maximum,
            names=names,
            version=version,
            started=started,
            observed=now,
            collected=collected,
            fresh=fresh,
            live=live,
            api_online=api_online,
            waiting=waiting,
            graceful_stop=server.get("stop_command", "").strip() == "stop"
            if isinstance(server.get("stop_command"), str)
            else False,
        )

    def _reconcile(self, result: Snapshot) -> Snapshot:
        pending = self.store.value.get("pending")
        if not pending:
            return result
        target = pending["action"] == "start_server"
        if target:
            after = (
                result.collected is not None
                and result.collected.timestamp() > pending["sent_at"]
            )
        else:
            after = (
                result.observed is not None
                and result.observed.timestamp() > pending["sent_at"]
            )
        confirmed = (
            result.crafty_ok
            and after
            and not result.waiting
            and result.running is target
            and (
                (target and result.fresh and result.live is not None)
                or (not target and result.live is None)
            )
        )
        if confirmed:
            self.store.set(pending=None)
            log.info("operation_reconciled action=%s", pending["action"])
            return result
        timeout = self.config.start_timeout if target else self.config.stop_timeout
        expired = time.time() - pending["sent_at"] > timeout
        if not result.crafty_ok:
            return result
        return replace(
            result,
            state=State.UNAVAILABLE if expired else (State.STARTING if target else State.STOPPING),
            detail="Resultado incerto; controles bloqueados"
            if expired
            else "Conectado; aguardando confirmação da operação",
        )
