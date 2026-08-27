import threading

from gpiozero import OutputDevice

from config import GPIO_PIN
from database import update_state, add_event


class FanController:
    def __init__(self):
        self.relay = OutputDevice(
            GPIO_PIN,
            active_high=True,
            initial_value=False
        )
        self.lock = threading.Lock()

    @property
    def is_on(self):
        return self.relay.is_active

    def turn_on(self, reason="Manual"):
        with self.lock:
            if not self.relay.is_active:
                self.relay.on()
                update_state(fan_state=1)
                add_event("FAN", f"Fan ON - {reason}")

    def turn_off(self, reason="Manual"):
        with self.lock:
            if self.relay.is_active:
                self.relay.off()
                update_state(fan_state=0)
                add_event("FAN", f"Fan OFF - {reason}")

    def cleanup(self):
        with self.lock:
            self.relay.off()
            self.relay.close()
