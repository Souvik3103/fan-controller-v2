import time
import threading

from config import MAX_RUNTIME_SECONDS
from database import get_state, update_state, add_event


class TimerManager:
    def __init__(self, fan):
        self.fan = fan
        self.lock = threading.Lock()

    def start(self, duration):
        duration = int(duration)

        if duration <= 0:
            raise ValueError("Timer must be greater than zero.")

        if duration > MAX_RUNTIME_SECONDS:
            raise ValueError("Timer exceeds maximum allowed runtime.")

        end = time.time() + duration

        with self.lock:
            self.fan.turn_on("Timer started")
            update_state(
                control_mode="timer",
                timer_end=end,
                cooldown_end=None
            )
            add_event("TIMER", f"Timer started: {duration} seconds")

    def cancel(self):
        state = get_state()

        if state["control_mode"] != "timer":
            return

        with self.lock:
            update_state(
                control_mode="manual",
                timer_end=None
            )
            self.fan.turn_off("Timer cancelled")

    def remaining(self):
        state = get_state()

        if state["control_mode"] != "timer" or state["timer_end"] is None:
            return 0

        return max(0, int(state["timer_end"] - time.time()))

    def check(self):
        state = get_state()

        if state["control_mode"] != "timer" or state["timer_end"] is None:
            return

        if time.time() >= state["timer_end"]:
            update_state(
                control_mode="manual",
                timer_end=None
            )
            self.fan.turn_off("Timer completed")
