"""Storage layer for sensors and readings.

The backing store is an implementation detail (in-memory dict, SQLite,
something else). The interface below is what the rest of the server uses.
"""
from __future__ import annotations

import sqlite3
import asyncio
from typing import Iterable, Optional


class Storage:
    """SQLite-backed storage for sensors and readings."""

    def __init__(self, db_path: str = "telemetry.db") -> None:
        """Initialize the storage layer with a SQLite database."""
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Create sensors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                sensor_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                interval_seconds REAL NOT NULL,
                location TEXT,
                created_at REAL NOT NULL
            )
        """)

        # Create readings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp INTEGER NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (sensor_id) REFERENCES sensors(sensor_id)
            )
        """)

        # Create index for faster time-range queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_readings_sensor_timestamp
            ON readings(sensor_id, timestamp)
        """)

        conn.commit()
        conn.close()

    async def add_sensor(self, sensor: dict) -> None:
        """Register a new sensor."""
        import time
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO sensors 
                    (sensor_id, type, interval_seconds, location, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    sensor["sensor_id"],
                    sensor["type"],
                    sensor.get("interval_seconds", 10),
                    sensor.get("location", ""),
                    time.time(),
                ))
                conn.commit()
            finally:
                conn.close()

    async def remove_sensor(self, sensor_id: str) -> None:
        """Remove a sensor and its readings."""
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # Remove readings first (foreign key constraint)
                cursor.execute("DELETE FROM readings WHERE sensor_id = ?", (sensor_id,))
                # Remove sensor
                cursor.execute("DELETE FROM sensors WHERE sensor_id = ?", (sensor_id,))
                conn.commit()
            finally:
                conn.close()

    async def list_sensors(self) -> Iterable:
        """Return all registered sensors."""
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT * FROM sensors ORDER BY created_at DESC")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def add_reading(self, reading: dict) -> None:
        """Persist a single reading."""
        import time
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO readings 
                    (sensor_id, type, value, timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    reading["sensor_id"],
                    reading["type"],
                    reading["value"],
                    reading["timestamp"],
                    time.time(),
                ))
                conn.commit()
            finally:
                conn.close()

    async def get_readings(
        self,
        sensor_id: str,
        from_ts: Optional[float] = None,
        to_ts: Optional[float] = None,
    ) -> Iterable:
        """Return readings for a sensor within an optional time window."""
        async with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                query = "SELECT * FROM readings WHERE sensor_id = ?"
                params = [sensor_id]

                if from_ts is not None:
                    query += " AND timestamp >= ?"
                    params.append(int(from_ts))

                if to_ts is not None:
                    query += " AND timestamp <= ?"
                    params.append(int(to_ts))

                query += " ORDER BY timestamp DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
