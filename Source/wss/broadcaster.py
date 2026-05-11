"""Tracks connected WebSocket clients and dispatches readings to them.

Owns the set of live clients, their subscription filters, and a way for
producers (the telemetry server) to publish a new reading.
"""
from __future__ import annotations
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class Broadcaster:
    """Fan-out of readings to the set of connected WebSocket clients."""

    def __init__(self) -> None:
        self._clients       = {}   # websocket -> set of sensor_ids (empty = all)
        self._lock          = asyncio.Lock()

    async def register(self, websocket) -> None:
        """Add a newly connected client."""
        async with self._lock:
            self._clients[websocket] = set()
            logger.info(f"Client registered. Total: {len(self._clients)}")

    async def unregister(self, websocket) -> None:
        """Remove a disconnected client."""
        async with self._lock:
            self._clients.pop(websocket, None)
            logger.info(f"Client unregistered. Total: {len(self._clients)}")

    async def set_subscription(self, websocket, sensor_ids) -> None:
        """Replace the per-client sensor-id filter."""
        async with self._lock:
            self._clients[websocket] = set(sensor_ids)
            logger.info(f"Subscription updated for client: {sensor_ids}")

    async def publish(self, reading) -> None:
        """Push a reading to every interested client.

        Be careful with slow consumers — a blocked client must not stall
        delivery to the rest. Document the strategy you choose
        (drop, buffer-with-bound, disconnect, etc.) in the architecture
        document.
        """
        message = json.dumps({
            "sensor_id": reading["sensor_id"],
            "type":      reading["type"],
            "value":     reading["value"],
            "ts":        reading["timestamp"],
        })

        async with self._lock:
            clients = dict(self._clients)

        disconnected = []

        async def send_to(ws, subs):
            # Empty subscription set means subscribed to all sensors
            if subs and reading["sensor_id"] not in subs:
                return
            try:
                await asyncio.wait_for(ws.send(message), timeout=2.0)
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning(f"Failed to send to client: {e}")
                disconnected.append(ws)

        await asyncio.gather(*[send_to(ws, subs) for ws, subs in clients.items()])

        # Clean up disconnected clients
        async with self._lock:
            for ws in disconnected:
                self._clients.pop(ws, None)
