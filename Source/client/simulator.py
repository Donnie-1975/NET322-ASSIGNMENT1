"""Single-sensor simulation logic.

Each simulated sensor:
  - Connects to the telemetry server over TCP.
  - Generates plausible readings on its configured interval.
  - Encodes each reading as a Protobuf message and writes a length-prefixed
    frame on the socket.
  - Reconnects with backoff after transient network failures.
"""
from __future__ import annotations
import asyncio
import random
import struct
import time
import logging
from proto import telemetry_pb2

logger = logging.getLogger(__name__)


class SensorSimulator:
    """Simulates one sensor pushing readings to the telemetry server."""

    def __init__(
        self,
        sensor_id: str,
        sensor_type: str,
        interval_seconds: float,
        host: str,
        port: int,
        range_min: float = 0.0,
        range_max: float = 100.0,
    ) -> None:
        self.sensor_id        = sensor_id
        self.sensor_type      = sensor_type
        self.interval_seconds = interval_seconds
        self.host             = host
        self.port             = port
        self.range_min        = range_min
        self.range_max        = range_max
        self._current_value   = random.uniform(range_min, range_max)

    async def run(self) -> None:
        """Connect, then push readings on the configured interval forever."""
        backoff = 1
        while True:
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                logger.info(f"[{self.sensor_id}] Connected to {self.host}:{self.port}")
                backoff = 1

                while True:
                    reading = self._generate_reading()
                    payload = reading.SerializeToString()
                    frame   = struct.pack(">I", len(payload)) + payload
                    writer.write(frame)
                    await writer.drain()
                    logger.info(f"[{self.sensor_id}] Sent reading: {reading.value:.2f}")
                    await asyncio.sleep(self.interval_seconds)

            except (ConnectionRefusedError, OSError) as e:
                logger.warning(f"[{self.sensor_id}] Connection failed: {e}. Retrying in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)

    def _generate_reading(self):
        """Produce a plausible next Reading for this sensor."""
        # Random walk — small drift up or down each time
        drift = random.uniform(-1.0, 1.0)
        self._current_value += drift
        self._current_value  = max(self.range_min, min(self.range_max, self._current_value))

        type_map = {
            "temperature":   telemetry_pb2.ReadingType.TEMPERATURE,
            "humidity":      telemetry_pb2.ReadingType.HUMIDITY,
            "soil_moisture": telemetry_pb2.ReadingType.SOIL_MOISTURE,
            "light":         telemetry_pb2.ReadingType.LIGHT,
        }

        reading = telemetry_pb2.Reading()
        reading.sensor_id = self.sensor_id
        reading.type      = type_map.get(self.sensor_type, telemetry_pb2.ReadingType.UNKNOWN)
        reading.value     = round(self._current_value, 2)
        reading.timestamp = int(time.time())
        return reading
