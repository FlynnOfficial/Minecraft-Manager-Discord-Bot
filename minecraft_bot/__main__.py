from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import signal
import ssl
from pathlib import Path

from .bot import MinecraftBot
from .config import Config
from .crafty import CraftyClient
from .logging_setup import configure
from .monitor import Monitor
from .operations import Operations
from .status import StatusProbe
from .storage import InstanceLock, Store


class DiagnosticError(Exception):
    """Only application-authored messages, never raw API/exception payloads."""


def make_store(config: Config) -> Store:
    return Store(
        config.data_dir,
        {"guild": config.guild_id, "channel": config.channel_id, "server": config.server_id},
    )


async def run(config: Config) -> None:
    store = make_store(config)
    stop_file = config.data_dir / "stop.request"
    stop_file.unlink(missing_ok=True)
    async with CraftyClient(config) as api:
        monitor = Monitor(config, api, StatusProbe(config), store)
        operations = Operations(config, api, monitor, store)
        async with MinecraftBot(config, monitor, operations, store) as bot:
            stopping = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stopping.set))

            async def watch_stop() -> None:
                while not stopping.is_set() and not stop_file.exists():
                    try:
                        await asyncio.wait_for(stopping.wait(), timeout=2)
                    except TimeoutError:
                        pass
                await bot.close()

            bot_task = asyncio.create_task(bot.start(config.discord_token, reconnect=True))
            stop_task = asyncio.create_task(watch_stop())
            try:
                while not bot_task.done():
                    watched = {bot_task, stop_task}
                    if bot.worker:
                        watched.add(bot.worker)
                    done, _ = await asyncio.wait(
                        watched, timeout=2, return_when=asyncio.FIRST_COMPLETED
                    )
                    if bot.worker and bot.worker in done and not bot.worker.cancelled():
                        error = bot.worker.exception()
                        if error:
                            raise error
                    if stop_task in done:
                        await stop_task
                        break
                await bot_task
            finally:
                stop_task.cancel()
                bot_task.cancel()
                await asyncio.gather(stop_task, bot_task, return_exceptions=True)


async def doctor(config: Config, listing: bool = False) -> None:
    async with CraftyClient(config) as api:
        servers = await api.servers()
        if not servers:
            raise DiagnosticError(
                "Conexao com Crafty OK, mas este token nao tem servidores acessiveis. "
                "Em Panel Settings, associe o usuario dono da chave a um cargo com "
                "acesso ao Minecraft. Confira COMMANDS no cargo e na chave API."
            )
        if listing:
            for server in servers:
                print(f"{server.get('server_id')}  {str(server.get('server_name', ''))[:100]}")
            return
        if not any(str(s.get("server_id")) == config.server_id for s in servers):
            raise DiagnosticError(
                "O servidor configurado nao aparece entre os acessiveis. "
                "Execute list-servers, confira CRAFTY_SERVER_ID e o cargo do usuario no Crafty."
            )
        monitor = Monitor(config, api, StatusProbe(config), make_store(config))
        snapshot = await monitor.refresh()
        print(f"Crafty instalado (informado): {config.crafty_version}")
        print(f"API: {snapshot.detail}; estado: {snapshot.state}; dados recentes: {snapshot.fresh}")
        print(f"Status local respondeu: {snapshot.live is not None}")
        print("Diagnostico somente leitura: nenhuma acao de energia foi enviada.")
        if not snapshot.crafty_ok or not snapshot.fresh:
            raise DiagnosticError(
                "Contrato ou conectividade nao validado; veja o diagnostico acima."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=[
            "run",
            "check",
            "doctor",
            "list-servers",
            "stop",
            "cert-fingerprint",
            "clear-pending",
        ],
        nargs="?",
        default="run",
    )
    parser.add_argument("--file", type=Path)
    parser.add_argument("--verified-in-crafty", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "cert-fingerprint":
            if not args.file:
                raise ValueError("Informe --file com o certificado PUBLICO local do Crafty.")
            raw = args.file.read_bytes()
            if b"-----BEGIN CERTIFICATE-----" in raw:
                raw = ssl.PEM_cert_to_DER_cert(raw.decode("ascii"))
            print(hashlib.sha256(raw).hexdigest())
            return 0
        config = Config.load()
        configure(config.log_dir, (config.discord_token, config.crafty_token))
        if args.command == "stop":
            config.data_dir.mkdir(parents=True, exist_ok=True)
            (config.data_dir / "stop.request").touch()
            return 0
        if args.command == "check":
            make_store(config)
            print("Configuracao local valida. Credenciais e integracoes ainda nao verificadas.")
            return 0
        with InstanceLock(config.data_dir):
            if args.command == "clear-pending":
                if not args.verified_in_crafty:
                    raise ValueError("Verifique manualmente o Crafty e use --verified-in-crafty.")
                make_store(config).set(pending=None)
                logging.getLogger("audit").warning("pending_cleared_locally_by_operator")
            elif args.command in {"doctor", "list-servers"}:
                asyncio.run(doctor(config, listing=args.command == "list-servers"))
            else:
                asyncio.run(run(config))
        return 0
    except DiagnosticError as error:
        logging.getLogger(__name__).error("diagnostic_failed reason=%s", error)
        print(f"Diagnostico: {error}")
        return 1
    except (Exception, KeyboardInterrupt) as error:
        logging.getLogger(__name__).error("fatal type=%s", type(error).__name__)
        print(f"Falha ({type(error).__name__}). Confira .env, README e logs/bot.jsonl.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
