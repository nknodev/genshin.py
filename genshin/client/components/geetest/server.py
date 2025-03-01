"""Aiohttp webserver used for login."""
from __future__ import annotations

import asyncio
import typing
import webbrowser

import aiohttp
from aiohttp import web
import random
from genshin.utility import geetest

from . import client

__all__ = ["login_with_app"]

INDEX = """
<!DOCTYPE html>
<html>
  <body>
    <button type="button" id="login">Login</button>
  </body>
  <script src="./gt.js"></script>
  <script>
    fetch("/mmt")
      .then((response) => response.json())
      .then((mmt) =>
        window.initGeetest(
          {
            gt: mmt.gt,
            challenge: mmt.challenge,
            new_captcha: mmt.new_captcha,
            api_server: "api-na.geetest.com",
            lang: "en",
            product: "bind",
            https: false,
          },
          (captcha) => {
            captcha.appendTo("login");
            captcha.onSuccess(() => {
              fetch("/login", {
                method: "POST",
                body: JSON.stringify(captcha.getValidate()),
              });
              document.body.innerHTML = "you may now close this window";
            });
            document.getElementById("login").onclick = () => {
              return captcha.verify();
            };
          }
        )
      );
  </script>
</html>
"""

GT_URL = "https://raw.githubusercontent.com/GeeTeam/gt3-node-sdk/master/demo/static/libs/gt.js"


async def login_with_app(client: client.GeetestClient, account: str, password: str, *, port: int = 5000) -> typing.Any:
    """Create and run an application for handling login."""
    routes = web.RouteTableDef()
    future: asyncio.Future[typing.Any] = asyncio.Future()

    mmt_key: str = ""

    @routes.get("/")
    async def index(request: web.Request) -> web.StreamResponse:
        return web.Response(body=INDEX, content_type="text/html")

    @routes.get("/gt.js")
    async def gt(request: web.Request) -> web.StreamResponse:
        async with aiohttp.ClientSession() as session:
            r = await session.get(GT_URL)
            content = await r.read()

        return web.Response(body=content, content_type="text/javascript")

    @routes.get("/mmt")
    async def mmt_endpoint(request: web.Request) -> web.Response:
        nonlocal mmt_key

        mmt = await geetest.create_mmt()
        mmt_key = mmt["mmt_key"]
        return web.json_response(mmt)

    @routes.post("/login")
    async def login_endpoint(request: web.Request) -> web.Response:
        body = await request.json()

        try:
            data = await client.login_with_geetest(
                account=account,
                password=password,
                mmt_key=mmt_key,
                geetest=body,
            )
        except Exception as e:
            future.set_exception(e)
            return web.json_response({}, status=500)

        future.set_result(data)

        return web.json_response(data)

    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()
    
    portr = random.randint(1000, 10000)
    site = web.TCPSite(runner, host="localhost", port=portr)
    print('opened on ' + portr)


    await site.start()

    try:
        data = await future
    finally:
        await asyncio.sleep(0.3)
        await runner.shutdown()

    return data
