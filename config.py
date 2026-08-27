import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(os.path.join(BASE_DIR, ".env"))

GPIO_PIN = int(os.getenv("GPIO_PIN", "17"))

DATABASE = os.path.join(BASE_DIR, "data", "fan.db")

MAX_RUNTIME_SECONDS = int(os.getenv("MAX_RUNTIME_HOURS", "8")) * 3600

BAMBU_MQTT_HOST = os.getenv("BAMBU_MQTT_HOST", "us.mqtt.bambulab.com")
BAMBU_MQTT_PORT = int(os.getenv("BAMBU_MQTT_PORT", "8883"))
BAMBU_USER_ID = os.getenv("BAMBU_USER_ID", "")
BAMBU_ACCESS_TOKEN = os.getenv("BAMBU_ACCESS_TOKEN", "")
BAMBU_DEVICE_ID = os.getenv("BAMBU_DEVICE_ID", "")

BAMBU_AUTO_FAN = os.getenv("BAMBU_AUTO_FAN", "true").lower() == "true"
BAMBU_FAN_WHILE_PRINTING = os.getenv("BAMBU_FAN_WHILE_PRINTING", "true").lower() == "true"
BAMBU_FAN_ON_ERROR = os.getenv("BAMBU_FAN_ON_ERROR", "true").lower() == "true"
BAMBU_COOLDOWN_MINUTES = int(os.getenv("BAMBU_COOLDOWN_MINUTES", "30"))

TEMPERATURE_HISTORY_SECONDS = int(os.getenv("TEMPERATURE_HISTORY_SECONDS", "10"))
