"""Entry point for the telemetry server.

Run with:
    python -m server
"""
from __future__ import annotations

import asyncio
import logging
from aiohttp import web
from server.storage import Storage
from server.tcp_ingest import start_tcp_server
from server.rest_api import build_app
instance: Storage | None = None

async def main() -> None:
    """Boot the telemetry server.

    Responsibilities:
      - Initialise the storage layer.
      - Start the TCP ingest listener for sensor connections.
      - Start the aiohttp app hosting the REST API.
      - Wait until shutdown.
    """

    logging.basicConfig(level=logging.INFO)

    # Initialise storage and make it available globally
    import server
    server.instance = Storage()

    # Start the TCP ingest server on port 9000
    tcp_server = await start_tcp_server(
        host="127.0.0.1",
        port=9000,
        storage=server.instance,
        broadcaster=None,
    )

    # Start the REST API on port 8080
    app = build_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="127.0.0.1", port=8080)
    await site.start()

    logging.info("Server ready — TCP on :9000 | REST on :8080")

    # Run forever
    async with tcp_server:
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
