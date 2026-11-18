import os
import sys
from pathlib import Path

os.environ["FRESHSENSE_DB"] = ":memory:"
os.environ["FRESHSENSE_MQTT_ENABLED"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
