"""Push a batch of synthetic telemetry events to the running app.

Usage:
    docker compose exec app python -m scripts.seed_telemetry --count 500
"""
from __future__ import annotations

import argparse
import asyncio
import random
from datetime import UTC, datetime

import httpx

SENSORS = [f"sensor-{i:02d}" for i in range(1, 11)]
KINDS = ["temperature", "humidity", "smoke", "wind", "particulate"]
LOCATIONS = [f"grid-{c}-{n}" for c in "ABCDE" for n in range(1, 5)]
NOTES = [
    "stable baseline",
    "slight uptick after sunrise",
    "sharp spike near treeline",
    "intermittent drop",
    "elevated relative to neighbors",
    None,
    None,
]


def make_event() -> dict:
    return {
        "sensor_id": random.choice(SENSORS),
        "kind": random.choice(KINDS),
        "value": round(random.uniform(0, 100), 2),
        "location": random.choice(LOCATIONS),
        "notes": random.choice(NOTES),
    }


async def main(count: int, base_url: str) -> None:
    started = datetime.now(UTC)
    async with httpx.AsyncClient(base_url=base_url, timeout=10) as client:
        for i in range(count):
            ev = make_event()
            resp = await client.post("/telemetry", json=ev)
            if resp.status_code >= 400:
                print(f"[{i}] {resp.status_code} {resp.text}")
            if i % 50 == 0 and i > 0:
                print(f"... {i} events")
    elapsed = (datetime.now(UTC) - started).total_seconds()
    print(f"pushed {count} events in {elapsed:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()
    asyncio.run(main(args.count, args.base_url))
