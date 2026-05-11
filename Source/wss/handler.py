"""WebSocket connection handler at /live.

One coroutine per connected client. Reads optional subscription messages
from the client and otherwise just forwards readings published by the
broadcaster.
"""
from __future__ import annotations
import json
import logging
from wss.broadcaster import Broadcaster

logger = logging.getLogger(__name__)
broadcaster: Broadcaster | None = None


async def live(websocket, path: str) -> None:
    """Handle one WebSocket client connection."""

    # Register the new client
    await broadcaster.register(websocket)
    logger.info("New WebSocket client connected.")

    try:
        async for message in websocket:
            try:
                data = json.loads(message)

                # Handle subscription messages from the client
                if data.get("action") == "subscribe":
                    sensor_ids = data.get("sensors", [])
                    await broadcaster.set_subscription(websocket, sensor_ids)
                    logger.info(f"Client subscribed to: {sensor_ids}")

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from client — ignoring.")

    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")

    finally:
        # Always unregister on disconnect
        await broadcaster.unregister(websocket)
        logger.info("WebSocket client disconnected.")
