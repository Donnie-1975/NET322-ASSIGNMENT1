"""Asynchronous TCP listener for sensor connections.

Sensors connect over TCP and stream Protobuf-encoded readings.
Framing: 4-byte big-endian length prefix followed by the Protobuf payload.
"""
from __future__ import annotations

import asyncio
import struct
import time
import logging

from server.storage import Storage
from proto import telemetry_pb2

logger = logging.getLogger(__name__)

# These are set by __main__.py before the server starts
_storage: Storage | None = None
_broadcaster = None


def init(storage: Storage, broadcaster) -> None:
    """Inject the storage and broadcaster instances."""
    global _storage, _broadcaster
    _storage = storage
    _broadcaster = broadcaster


async def handle_sensor(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    """Handle one sensor connection until it closes."""
    peer = writer.get_extra_info("peername")
    logger.info(f"Sensor connected from {peer}")

    try:
        while True:
            # --- 1. Read the 4-byte length prefix ---
            header = await reader.readexactly(4)
            msg_len = struct.unpack(">I", header)[0]

            # --- 2. Read exactly that many bytes ---
            payload = await reader.readexactly(msg_len)

            # --- 3. Decode the Protobuf Reading message ---
            reading_proto = telemetry_pb2.Reading()
            reading_proto.ParseFromString(payload)

            # --- 4. Convert to a plain dict ---
            reading = {
                "sensor_id": reading_proto.sensor_id,
                "type":      telemetry_pb2.ReadingType.Name(reading_proto.type),
                "value":     reading_proto.value,
                "timestamp": reading_proto.timestamp or int(time.time()),
            }

            logger.info(f"Reading received: {reading}")

            # --- 5. Persist to storage ---
            await _storage.add_reading(reading)

            # --- 6. Publish to WebSocket broadcaster if available ---
            if _broadcaster is not None:
                await _broadcaster.publish(reading)

    except asyncio.IncompleteReadError:
        logger.info(f"Sensor {peer} disconnected.")
    except Exception as e:
        logger.warning(f"Error handling sensor {peer}: {e}")
    finally:
        writer.close()
        await writer.wait_closed()


async def start_tcp_server(host: str, port: int, storage: Storage, broadcaster) -> asyncio.AbstractServer:
    """Start the TCP ingest server listening on (host, port)."""
    init(storage, broadcaster)
    server = await asyncio.start_server(handle_sensor, host, port)
    logger.info(f"TCP ingest server listening on {host}:{port}")
    return server