import json
import ssl
import threading
import time

import paho.mqtt.client as mqtt

from config import (
    BAMBU_MQTT_HOST,
    BAMBU_MQTT_PORT,
    BAMBU_USER_ID,
    BAMBU_ACCESS_TOKEN,
    BAMBU_DEVICE_ID
)


STAGE_NAMES = {
    0: None,
    1: "Auto Bed Leveling",
    2: "Preheating Heatbed",
    3: "Vibration Compensation",
    4: "Changing Filament",
    5: "M400 Pause",
    6: "Filament Runout",
    7: "Heating Hotend",
    8: "Calibrating Extrusion",
    9: "Scanning Bed Surface",
    10: "Inspecting First Layer",
    11: "Identifying Build Plate",
    12: "Calibrating Micro Lidar",
    13: "Homing Toolhead",
    14: "Cleaning Nozzle",
    15: "Checking Extruder Temperature",
    16: "Paused by User",
    17: "Front Cover Error",
    18: "Calibrating Micro Lidar",
    19: "Calibrating Extrusion Flow",
    20: "Nozzle Temperature Error",
    21: "Heatbed Temperature Error",
    22: "Unloading Filament",
    23: "Skipped Step",
    24: "Loading Filament",
    25: "Motor Noise Calibration",
    26: "AMS Connection Lost",
    27: "Low Fan Speed",
    28: "Chamber Temperature Error",
    29: "Cooling Chamber",
    30: "Paused by G-code",
    31: "Motor Noise Calibration",
    32: "Nozzle Filament Covered",
    33: "Cutter Error",
    34: "First Layer Error",
    35: "Nozzle Clog",
    36: "Checking Absolute Accuracy",
    37: "Absolute Accuracy Calibration",
    38: "Checking Absolute Accuracy",
    39: "Calibrating Nozzle Offset",
    40: "High Temperature Bed Leveling",
    41: "Checking Quick Release",
    42: "Checking Door / Cover",
    43: "Laser Calibration",
    44: "Checking Platform",
    45: "Checking Camera Position",
    46: "Calibrating Camera",
    47: "Bed Leveling Phase 1",
    48: "Bed Leveling Phase 2",
    49: "Heating Chamber",
    50: "Cooling Heatbed",
    51: "Printing Calibration Lines",
    52: "Checking Material",
    53: "Camera Calibration",
    54: "Waiting for Heatbed Temperature",
    55: "Checking Material Position",
    56: "Calibrating Cutter",
    57: "Measuring Surface",
    58: "Thermal Preconditioning",
    59: "Homing Blade Holder",
    60: "Calibrating Camera Offset",
    61: "Calibrating Blade Holder",
    62: "Testing Hotend",
    63: "Waiting for Chamber Temperature",
    64: "Preparing Hotend",
    65: "Calibrating Nozzle Detection",
    66: "Purifying Chamber Air",
    77: "Preparing AMS",
    255: None
}

GCODE_STATES = {
    "IDLE": "Idle",
    "PREPARE": "Preparing",
    "RUNNING": "Printing",
    "PAUSE": "Paused",
    "FINISH": "Print Finished",
    "FAILED": "Print Failed",
    "SLICING": "Slicing",
    "INIT": "Initializing",
    "OFFLINE": "Offline"
}


class BambuMonitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.client = None
        self.connected = False

        self.state = {
            "state": "UNKNOWN",
            "state_label": "Unknown",
            "stage": None,
            "stage_id": None,
            "activity": "Unknown",
            "progress": 0,
            "remaining_minutes": None,
            "current_layer": None,
            "total_layers": None,
            "nozzle_temperature": None,
            "nozzle_target_temperature": None,
            "bed_temperature": None,
            "bed_target_temperature": None,
            "chamber_temperature": None,
            "wifi_signal": None,
            "filename": None,
            "error": None,
            "error_code": None,
            "print_speed": None,
            "print_type": None,
            "last_update": None
        }

    def send_command(self, command, param=None):
        if not self.connected or self.client is None:
            raise RuntimeError("Bambu MQTT is not connected.")

        payload = {
            "print": {
                "sequence_id": str(int(time.time())),
                "command": command
            }
        }

        if param is not None:
            payload["print"]["param"] = param

        topic = f"device/{BAMBU_DEVICE_ID}/request"

        result = self.client.publish(
            topic,
            json.dumps(payload),
            qos=1
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed: {result.rc}")

        print("Bambu command sent:", command)

    def resume_print(self):
        self.send_command("resume")

    def pause_print(self):
        self.send_command("pause")

    def stop_print(self):
        self.send_command("stop")

    def get_state(self):
        with self.lock:
            result = dict(self.state)
            result["connected"] = self.connected
            return result

    @staticmethod
    def number(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def calculate_activity(self):
        state = self.state["state"]
        stage_id = self.state["stage_id"]
        stage = STAGE_NAMES.get(stage_id)

        if stage:
            return stage

        return GCODE_STATES.get(state, str(state).title())

    def parse_message(self, payload):
        try:
            data = json.loads(payload)
        except Exception:
            return

        report = data.get("print")
        if not report:
            return

        with self.lock:
            if "gcode_state" in report:
                value = report["gcode_state"]
                self.state["state"] = value
                self.state["state_label"] = GCODE_STATES.get(value, value)

            if "stg_cur" in report:
                try:
                    self.state["stage_id"] = int(report["stg_cur"])
                except (TypeError, ValueError):
                    pass

            if "mc_percent" in report:
                try:
                    self.state["progress"] = int(report["mc_percent"])
                except (TypeError, ValueError):
                    pass

            if "mc_remaining_time" in report:
                try:
                    self.state["remaining_minutes"] = int(report["mc_remaining_time"])
                except (TypeError, ValueError):
                    pass

            if "layer_num" in report:
                try:
                    self.state["current_layer"] = int(report["layer_num"])
                except (TypeError, ValueError):
                    pass

            if "total_layer_num" in report:
                try:
                    self.state["total_layers"] = int(report["total_layer_num"])
                except (TypeError, ValueError):
                    pass

            mappings = {
                "nozzle_temper": "nozzle_temperature",
                "nozzle_target_temper": "nozzle_target_temperature",
                "bed_temper": "bed_temperature",
                "bed_target_temper": "bed_target_temperature",
                "chamber_temper": "chamber_temperature"
            }

            for source, target in mappings.items():
                if source in report:
                    self.state[target] = self.number(report[source])

            if "gcode_file" in report and report["gcode_file"]:
                self.state["filename"] = report["gcode_file"]

            if "wifi_signal" in report:
                self.state["wifi_signal"] = report["wifi_signal"]

            if "print_type" in report:
                self.state["print_type"] = report["print_type"]

            if "spd_lvl" in report:
                self.state["print_speed"] = report["spd_lvl"]

            if "print_error" in report:
                error = report["print_error"]
                self.state["error_code"] = (
                    None if error in (None, 0, "0", "") else error
                )

            self.state["activity"] = self.calculate_activity()
            self.state["stage"] = STAGE_NAMES.get(self.state["stage_id"])
            self.state["last_update"] = time.time()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print("Bambu MQTT connected.")
            self.connected = True

            report_topic = f"device/{BAMBU_DEVICE_ID}/report"
            client.subscribe(report_topic)

            request_topic = f"device/{BAMBU_DEVICE_ID}/request"
            payload = json.dumps({
                "pushing": {
                    "sequence_id": "1",
                    "command": "pushall"
                }
            })
            client.publish(request_topic, payload)
            print("Requested full Bambu status.")
        else:
            print("Bambu MQTT failed:", reason_code)
            self.connected = False

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        print("Bambu MQTT disconnected:", reason_code)
        self.connected = False

    def on_message(self, client, userdata, message):
        payload = message.payload.decode("utf-8", errors="ignore")
        self.parse_message(payload)

    def connect_loop(self):
        while True:
            try:
                self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

                self.client.username_pw_set(
                    username=f"u_{BAMBU_USER_ID}",
                    password=BAMBU_ACCESS_TOKEN
                )

                self.client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

                self.client.on_connect = self.on_connect
                self.client.on_disconnect = self.on_disconnect
                self.client.on_message = self.on_message

                print(f"Connecting to {BAMBU_MQTT_HOST}:{BAMBU_MQTT_PORT}...")

                self.client.connect(
                    BAMBU_MQTT_HOST,
                    BAMBU_MQTT_PORT,
                    keepalive=60
                )

                self.client.loop_forever()

            except Exception as error:
                print("Bambu MQTT error:", error)
                self.connected = False
                time.sleep(10)

    def start(self):
        thread = threading.Thread(target=self.connect_loop, daemon=True)
        thread.start()
