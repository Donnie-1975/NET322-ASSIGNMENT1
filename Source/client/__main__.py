"""Entry point for the sensor simulator.

Run with:
    python -m client --config config/sensors.yaml
"""
from __future__ import annotations
import asyncio
import argparse
import logging
import yaml
from client.simulator import SensorSimulator

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Load the YAML config, spawn one task per sensor, run them all."""

    # Parse CLI args
    parser = argparse.ArgumentParser(description="Sensor Simulator")
    parser.add_argument(
        "--config",
        required=True,
        help="Path to sensors YAML config file"
    )
    args = parser.parse_args()

    # Load YAML config
    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    host = config["server"]["host"]
    port = config["server"]["port"]

    # Build one SensorSimulator per sensor entry
    tasks = []
    for sensor in config["sensors"]:
        sim = SensorSimulator(
            sensor_id        = sensor["id"],
            sensor_type      = sensor["type"],
            interval_seconds = sensor["interval_seconds"],
            host             = host,
            port             = port,
            range_min        = sensor.get("range", {}).get("min", 0.0),
            range_max        = sensor.get("range", {}).get("max", 100.0),
        )
        tasks.append(asyncio.create_task(sim.run()))

    logging.info(f"Starting {len(tasks)} sensor(s) → {host}:{port}")

    # Run all sensors concurrently forever
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
