"""Live tag input: MQTT (Wokwi ESP32) and HTTP (dashboard slider) share one latest reading."""
import json
import threading
import time

from config import LIVE_TAG_TIMEOUT_S, MQTT_ENABLED, MQTT_HOST, MQTT_PORT, MQTT_TOPIC

_lock = threading.Lock()
_latest: dict = {}
status = {"mqtt": "disabled", "topic": MQTT_TOPIC, "host": MQTT_HOST, "messages": 0}


def put_reading(data: dict):
    with _lock:
        _latest.clear()
        _latest.update(data)
        _latest["received_at"] = time.time()
        status["messages"] += 1


def get_latest():
    with _lock:
        if _latest and time.time() - _latest.get("received_at", 0) <= LIVE_TAG_TIMEOUT_S:
            return dict(_latest)
    return None


def clear():
    with _lock:
        _latest.clear()


def _on_connect(client, userdata, flags, reason_code, properties):
    status["mqtt"] = "connected"
    client.subscribe(MQTT_TOPIC)
    print(f"[mqtt] connected to {MQTT_HOST}, subscribed to {MQTT_TOPIC}")


def _on_disconnect(client, userdata, flags, reason_code, properties):
    status["mqtt"] = "disconnected"


def _on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        if isinstance(data, dict):
            put_reading(data)
    except Exception:
        pass


def start():
    if not MQTT_ENABLED:
        print("[mqtt] disabled by FRESHSENSE_MQTT_ENABLED=0")
        return
    try:
        import paho.mqtt.client as mqtt

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect
        client.on_message = _on_message
        client.connect_async(MQTT_HOST, MQTT_PORT)
        client.loop_start()
        status["mqtt"] = "connecting"
    except Exception as e:  # never crash the backend because of MQTT
        status["mqtt"] = f"error: {e}"
        print("[mqtt] disabled:", e)
