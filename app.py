from datetime import datetime, timedelta
import threading
import time
import platform

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO

from config import BAMBU_COOLDOWN_MINUTES
from database import (
    init_database,
    get_state,
    update_state,
    get_events,
    get_temperature_history,
    get_temperature_history_since,
    add_temperature,
    add_event,
    get_prints
)
from fan.controller import FanController
from fan.timer import TimerManager
from bambu.mqtt import BambuMonitor
from automation.engine import AutomationEngine


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

init_database()

fan = FanController()
timer = TimerManager(fan)
bambu = BambuMonitor()
automation = AutomationEngine(fan, timer, bambu)


def build_status():
    state = get_state()
    printer = bambu.get_state()

    remaining = printer.get("remaining_minutes")
    end_time = None

    if remaining is not None and printer.get("state") in (
        "PREPARE", "RUNNING", "SLICING", "INIT"
    ):
        end_time = (
            datetime.now() + timedelta(minutes=int(remaining))
        ).isoformat(timespec="minutes")

    return {
        "fan": {
            "on": fan.is_on,
            "mode": state["control_mode"],
            "timer_remaining": timer.remaining()
        },
        "printer": {
            **printer,
            "connected": bambu.connected,
            "estimated_end_time": end_time
        }
    }


@app.get("/")
def dashboard():
    return render_template("dashboard.html")


@app.get("/api/status")
def status():
    return jsonify(build_status())


@app.post("/api/fan/on")
def fan_on():
    update_state(
        control_mode="manual",
        timer_end=None,
        cooldown_end=None
    )
    fan.turn_on("Manual")
    return jsonify({"success": True})


@app.post("/api/fan/off")
def fan_off():
    update_state(
        control_mode="manual",
        timer_end=None,
        cooldown_end=None
    )
    fan.turn_off("Manual")
    return jsonify({"success": True})


@app.post("/api/timer")
def start_timer():
    data = request.get_json(silent=True) or {}

    try:
        hours = int(data.get("hours", 0))
        minutes = int(data.get("minutes", 0))
        seconds = int(data.get("seconds", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid timer values."}), 400

    if hours < 0 or minutes < 0 or minutes > 59 or seconds < 0 or seconds > 59:
        return jsonify({"error": "Invalid timer values."}), 400

    duration = hours * 3600 + minutes * 60 + seconds

    try:
        timer.start(duration)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify({"success": True})


@app.delete("/api/timer")
def cancel_timer():
    timer.cancel()
    return jsonify({"success": True})


@app.get("/api/settings")
def settings():
    state = get_state()

    return jsonify({
        "automation_enabled": bool(state["automation_enabled"]),
        "fan_while_printing": bool(state["fan_while_printing"]),
        "fan_on_error": bool(state["fan_on_error"]),
        "cooldown_minutes": state["cooldown_minutes"]
    })


@app.post("/api/settings")
def save_settings():
    data = request.get_json(silent=True) or {}

    try:
        automation_enabled = int(bool(data.get("automation_enabled", 1)))
        fan_while_printing = int(bool(data.get("fan_while_printing", 1)))
        fan_on_error = int(bool(data.get("fan_on_error", 1)))
        cooldown_minutes = int(
            data.get("cooldown_minutes", BAMBU_COOLDOWN_MINUTES)
        )
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid settings."}), 400

    if not 0 <= cooldown_minutes <= 240:
        return jsonify({"error": "Cooldown must be between 0 and 240 minutes."}), 400

    update_state(
        automation_enabled=automation_enabled,
        fan_while_printing=fan_while_printing,
        fan_on_error=fan_on_error,
        cooldown_minutes=cooldown_minutes
    )

    add_event("SETTINGS", "Automation settings updated")

    return jsonify({"success": True})


@app.get("/api/events")
def events():
    try:
        limit = int(request.args.get("limit", 10))
    except ValueError:
        limit = 10

    return jsonify(get_events(limit))


@app.get("/api/temperature")
def temperature():
    range_name = request.args.get("range", "1h")

    ranges = {
        "15m": 15 * 60,
        "1h": 60 * 60,
        "6h": 6 * 60 * 60,
        "24h": 24 * 60 * 60
    }

    if range_name not in ranges:
        return jsonify({"error": "Invalid range."}), 400

    return jsonify(
        get_temperature_history_since(ranges[range_name])
    )


@app.get("/api/prints")
def prints():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50

    return jsonify(get_prints(limit))


@app.get("/api/system")
def system_status():
    result = {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "uptime_seconds": None,
        "cpu_percent": None,
        "memory_percent": None,
        "disk_percent": None,
        "temperature": None
    }

    try:
        import psutil

        result["uptime_seconds"] = int(time.time() - psutil.boot_time())
        result["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        result["memory_percent"] = psutil.virtual_memory().percent
        result["disk_percent"] = psutil.disk_usage("/").percent

        temps = psutil.sensors_temperatures()
        for entries in temps.values():
            if entries:
                result["temperature"] = entries[0].current
                break
    except Exception:
        pass

    return jsonify(result)


@app.post("/api/mode")
def set_mode():
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "manual")

    if mode not in {"manual", "bambu"}:
        return jsonify({"error": "Invalid mode"}), 400

    update_state(
        control_mode=mode,
        timer_end=None,
        cooldown_end=None
    )

    if mode == "bambu":
        add_event("MODE", "Bambu Auto mode enabled")
    else:
        add_event("MODE", "Manual mode enabled")

    return jsonify({"success": True, "mode": mode})


@app.post("/api/printer/resume")
def resume_printer():
    printer = bambu.get_state()

    if printer["state"] != "PAUSE":
        return jsonify({
            "error": f"Printer is not paused. Current state: {printer['state']}"
        }), 400

    try:
        bambu.resume_print()
        add_event("PRINTER", "Resume command sent")
        return jsonify({"success": True})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.post("/api/printer/pause")
def pause_printer():
    printer = bambu.get_state()

    if printer["state"] != "RUNNING":
        return jsonify({
            "error": "Printer is not currently printing."
        }), 400

    try:
        bambu.pause_print()
        add_event("PRINTER", "Pause command sent")
        return jsonify({"success": True})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@app.post("/api/printer/stop")
def stop_printer():
    printer = bambu.get_state()

    if printer["state"] not in {"RUNNING", "PAUSE", "PREPARE"}:
        return jsonify({"error": "No active print to stop."}), 400

    try:
        bambu.stop_print()
        add_event("PRINTER", "STOP command sent")
        return jsonify({"success": True})
    except Exception as error:
        return jsonify({"error": str(error)}), 500


def dashboard_loop():
    last_temperature = 0

    while True:
        try:
            socketio.emit("status", build_status())

            if time.time() - last_temperature >= 10:
                printer = bambu.get_state()

                add_temperature(
                    printer["nozzle_temperature"],
                    printer["bed_temperature"],
                    printer["chamber_temperature"],
                    printer["state"]
                )

                last_temperature = time.time()

            time.sleep(1)

        except Exception as error:
            print("Dashboard loop error:", error)
            time.sleep(2)


if __name__ == "__main__":
    bambu.start()
    automation.start()

    dashboard_thread = threading.Thread(
        target=dashboard_loop,
        daemon=True
    )
    dashboard_thread.start()

    try:
        socketio.run(
            app,
            host="0.0.0.0",
            port=5001,
            allow_unsafe_werkzeug=True
        )
    finally:
        fan.cleanup()
