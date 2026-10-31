from __future__ import annotations

import json
import ssl
from typing import Literal

import aiohttp

from .config import Config


class CraftyError(Exception):
    """Only fixed, credential-free messages may cross this boundary."""

    def __init__(self, code: str, *, uncertain: bool = False):
        self.code = code
        self.uncertain = uncertain
        super().__init__(code)


class CraftyClient:
    def __init__(self, config: Config):
        self.config = config
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> CraftyClient:
        tls = (
            aiohttp.Fingerprint(bytes.fromhex(self.config.fingerprint))
            if self.config.fingerprint
            else ssl.create_default_context(cafile=self.config.ca_file)
        )
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.http_timeout),
            connector=aiohttp.TCPConnector(ssl=tls, limit=2),
            headers={"Authorization": f"Bearer {self.config.crafty_token}"},
            trust_env=False,
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self.session:
            await self.session.close()

    async def _request(self, method: str, path: str) -> object:
        assert self.session is not None
        mutation = method == "POST"
        try:
            async with self.session.request(
                method,
                self.config.crafty_url + "/api/v2" + path,
                allow_redirects=False,
            ) as response:
                if response.status in {401, 403}:
                    raise CraftyError("autenticacao_ou_permissao")
                if response.status == 404:
                    raise CraftyError("servidor_ou_endpoint_inexistente")
                if response.status >= 500 or response.status == 429:
                    raise CraftyError("api_temporariamente_indisponivel", uncertain=mutation)
                if not 200 <= response.status < 300 and response.status != 400:
                    raise CraftyError("requisicao_recusada", uncertain=mutation)
                raw = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    raw.extend(chunk)
                    if len(raw) > 1_048_576:
                        raise CraftyError("resposta_incompativel", uncertain=mutation)
                payload = json.loads(raw)
                if response.status == 400:
                    if isinstance(payload, dict) and payload.get("error") == "NOT_AUTHORIZED":
                        raise CraftyError("autenticacao_ou_permissao")
                    raise CraftyError("requisicao_recusada", uncertain=mutation)
                if not isinstance(payload, dict) or payload.get("status") != "ok":
                    if isinstance(payload, dict) and payload.get("error") == "NOT_AUTHORIZED":
                        raise CraftyError("autenticacao_ou_permissao")
                    raise CraftyError("resposta_incompativel", uncertain=mutation)
                return payload.get("data")
        except CraftyError:
            raise
        except (TimeoutError, aiohttp.ClientError, OSError):
            raise CraftyError("conexao_ou_tls", uncertain=mutation) from None
        except (ValueError, UnicodeError):
            raise CraftyError("resposta_incompativel", uncertain=mutation) from None

    async def servers(self) -> list[dict]:
        result = await self._request("GET", "/servers")
        if not isinstance(result, list) or not all(isinstance(x, dict) for x in result):
            raise CraftyError("resposta_incompativel")
        return result

    async def stats(self) -> dict:
        result = await self._request("GET", f"/servers/{self.config.server_id}/stats")
        if not isinstance(result, dict) or type(result.get("running")) is not bool:
            raise CraftyError("resposta_incompativel")
        return result

    async def action(self, action: Literal["start_server", "stop_server"]) -> None:
        if action not in {"start_server", "stop_server"}:
            raise ValueError("Acao nao permitida")
        await self._request("POST", f"/servers/{self.config.server_id}/action/{action}")
