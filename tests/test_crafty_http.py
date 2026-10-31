from dataclasses import replace

import pytest
from aiohttp import web

from minecraft_bot.crafty import CraftyClient, CraftyError


@pytest.fixture
async def endpoint(config):
    state = {
        "status": 200,
        "body": {"status": "ok", "data": {"running": True}},
        "calls": [],
        "headers": {},
        "redirect": False,
        "invalid": False,
    }

    async def handle(request):
        state["calls"].append((request.method, request.path))
        state["headers"] = dict(request.headers)
        if state["redirect"]:
            raise web.HTTPFound("/stolen")
        if state["invalid"]:
            return web.Response(text="SECRET_HTML_ERROR", content_type="text/html")
        return web.json_response(state["body"], status=state["status"])

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    local = replace(config, crafty_url=f"http://127.0.0.1:{port}")
    try:
        yield state, local
    finally:
        await runner.cleanup()


async def test_documented_endpoint_and_bearer(endpoint):
    state, config = endpoint
    async with CraftyClient(config) as api:
        assert (await api.stats())["running"] is True
        await api.action("start_server")
        await api.action("stop_server")
    assert state["headers"]["Authorization"] == "Bearer crafty-secret"
    assert state["calls"] == [
        ("GET", f"/api/v2/servers/{config.server_id}/stats"),
        ("POST", f"/api/v2/servers/{config.server_id}/action/start_server"),
        ("POST", f"/api/v2/servers/{config.server_id}/action/stop_server"),
    ]


@pytest.mark.parametrize(
    "status,code,uncertain",
    [
        (401, "autenticacao_ou_permissao", False),
        (403, "autenticacao_ou_permissao", False),
        (404, "servidor_ou_endpoint_inexistente", False),
        (429, "api_temporariamente_indisponivel", True),
        (500, "api_temporariamente_indisponivel", True),
    ],
)
async def test_http_failures_no_post_retries(endpoint, status, code, uncertain):
    state, config = endpoint
    state["status"] = status
    async with CraftyClient(config) as api:
        with pytest.raises(CraftyError) as caught:
            await api.action("stop_server")
    assert caught.value.code == code and caught.value.uncertain == uncertain
    assert len(state["calls"]) == 1


async def test_redirects_never_leak_token(endpoint):
    state, config = endpoint
    state["redirect"] = True
    async with CraftyClient(config) as api:
        with pytest.raises(CraftyError):
            await api.stats()
    assert len(state["calls"]) == 1


async def test_crafty_400_not_authorized_is_definite_rejection(endpoint):
    state, config = endpoint
    state.update(status=400, body={"status": "error", "error": "NOT_AUTHORIZED"})
    async with CraftyClient(config) as api:
        with pytest.raises(CraftyError) as caught:
            await api.action("stop_server")
    assert caught.value.code == "autenticacao_ou_permissao"
    assert not caught.value.uncertain


async def test_invalid_response_safe_error(endpoint):
    state, config = endpoint
    state["invalid"] = True
    async with CraftyClient(config) as api:
        with pytest.raises(CraftyError) as caught:
            await api.stats()
    assert "SECRET_HTML_ERROR" not in str(caught.value)


async def test_bool_string_not_silently_truthy(endpoint):
    state, config = endpoint
    state["body"]["data"]["running"] = "false"
    async with CraftyClient(config) as api:
        with pytest.raises(CraftyError, match="incompativel"):
            await api.stats()


async def test_arbitrary_actions_disallowed(endpoint):
    state, config = endpoint
    async with CraftyClient(config) as api:
        with pytest.raises(ValueError):
            await api.action("kill_server")
    assert not state["calls"]


async def test_client_timeout_is_uncertain_for_post(config):
    class TimeoutSession:
        def request(self, *args, **kwargs):
            raise TimeoutError("secret-library-message")

    api = CraftyClient(config)
    api.session = TimeoutSession()
    with pytest.raises(CraftyError) as caught:
        await api.action("start_server")
    assert caught.value.uncertain
    assert "secret" not in str(caught.value)
