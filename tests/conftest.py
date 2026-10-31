"""Fake adapter that replays recorded responses and enforces the CSRF check."""

import asyncio
import json
import pathlib
import sys

import pytest_asyncio
from aiohttp import web

ROOT = pathlib.Path(__file__).resolve().parents[1]
# import the API client without importing Home Assistant
sys.path.insert(0, str(ROOT / "custom_components" / "kiwee"))

from pykiwee.client import KiweeClient  # noqa: E402

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def adapter():
    """Return a factory: adapter("controller") -> client talking to a fake adapter."""
    runners: list[web.AppRunner] = []
    clients: list[KiweeClient] = []

    async def make(name: str, reboot: str = "hang") -> KiweeClient:
        """reboot: how the fake answers the reboot request - "hang" (no answer, like the real
        adapter), "drop" (closes the connection), "ok" (HTTP 200) or "reject" (HTTP 500)."""
        table = json.loads((FIXTURES / f"{name}.json").read_text())
        reboot_calls: list[str] = []

        async def page(_request):
            response = web.Response(text="<html></html>", content_type="text/html")
            response.set_cookie("csrf_token", "TESTTOKEN")
            return response

        async def ms(request):
            token = request.headers.get("X-CSRF-TOKEN")
            if not token or token != request.cookies.get("csrf_token"):
                return web.Response(status=400, text="Bad request")
            body = (await request.text()).replace(" ", "").strip() or '{"data":[]}'
            data = table.get(f"{request.path}|{body}")
            if data is None:
                return web.Response(status=400, text="Bad request")
            return web.json_response({"data": data})

        async def reboot_handler(request):
            token = request.headers.get("X-CSRF-TOKEN")
            if not token or token != request.cookies.get("csrf_token"):
                return web.Response(status=400, text="Bad request")
            reboot_calls.append((await request.text()).strip())
            if reboot == "reject":
                return web.Response(status=500, text="error")
            if reboot == "ok":
                return web.json_response({"data": []})
            if reboot == "hang":
                await asyncio.sleep(2)  # never answers within the client's timeout
                return web.Response()
            request.transport.close()  # "drop": the adapter just goes away
            return web.Response()

        app = web.Application()
        app.router.add_get("/devStatus.html", page)
        app.router.add_post("/ms/1/0xb00", reboot_handler)
        app.router.add_route("*", "/ms/{tail:.*}", ms)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        runners.append(runner)
        port = runner.addresses[0][1]
        client = KiweeClient(f"127.0.0.1:{port}")
        client.reboot_calls = reboot_calls  # for the tests
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.close()
    for runner in runners:
        await runner.cleanup()
