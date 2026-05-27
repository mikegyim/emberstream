"""Alternative ingestion path: read MQTT and forward to the REST endpoint.

This is intentionally a thin shim so the README can demonstrate that an MQTT
broker would slot cleanly in front of the REST API in a real deployment.

Usage:
    pip install paho-mqtt
    python scripts/mqtt_publisher.py --broker mqtt://localhost:1883 --topic telemetry
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse

import httpx

try:
    import paho.mqtt.client as mqtt
except ImportError:
    raise SystemExit("paho-mqtt is not installed. Run: pip install paho-mqtt")


def main(broker: str, topic: str, target: str) -> None:
    parsed = urlparse(broker)
    client = mqtt.Client()

    def on_message(_client, _userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except Exception as exc:
            print(f"skipping non-JSON message: {exc}")
            return
        resp = httpx.post(f"{target}/telemetry", json=payload, timeout=5)
        print(f"-> {resp.status_code}")

    client.on_message = on_message
    client.connect(parsed.hostname or "localhost", parsed.port or 1883)
    client.subscribe(topic)
    print(f"listening on {broker}/{topic}, forwarding to {target}/telemetry")
    client.loop_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="mqtt://localhost:1883")
    parser.add_argument("--topic", default="telemetry")
    parser.add_argument("--target", default="http://localhost:8000")
    args = parser.parse_args()
    main(args.broker, args.topic, args.target)
