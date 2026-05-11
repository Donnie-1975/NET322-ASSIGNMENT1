"""Entry point for the WebSocket live-feed server.

Run with:
    python -m wss
"""
from __future__ import annotations

import asyncio
import logging
import websockets
from wss.broadcaster import Broadcaster
import wss.handler as handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Boot the WebSocket server."""

    # Build the broadcaster and inject into handler
    broadcaster = Broadcaster()
    handler.broadcaster = broadcaster

    # Poll the SQLite database for new readings and publish them
    async def poll_readings():
        from server.storage import Storage
        storage = Storage()
        last_seen_id = 0

        while True:
            try:
                async with storage._lock:
                    import sqlite3
                    conn = sqlite3.connect("telemetry.db")
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        "SELECT * FROM readings WHERE id > ? ORDER BY id ASC",
                        (last_seen_id,)
                    ).fetchall()
                    conn.close()

                for row in rows:
                    reading = dict(row)
                    await broadcaster.publish(reading)
                    last_seen_id = reading["id"]

            except Exception as e:
                logger.warning(f"Poll error: {e}")

            await asyncio.sleep(1)

    # Start the polling task
    asyncio.create_task(poll_readings())

    # Start the WebSocket server on port 8765
    async with websockets.serve(handler.live, "127.0.0.1", 8765):
        logger.info("WebSocket server running on ws://127.0.0.1:8765/live")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
