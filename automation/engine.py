import threading
import time

from config import BAMBU_AUTO_FAN, BAMBU_FAN_WHILE_PRINTING, BAMBU_FAN_ON_ERROR
from database import (
    get_state,
    update_state,
    add_event,
    start_print,
    finish_print
)


class AutomationEngine:
    ACTIVE_STATES = {"PREPARE", "RUNNING", "SLICING", "INIT"}

    def __init__(self, fan, timer, bambu):
        self.fan = fan
        self.timer = timer
        self.bambu = bambu

        self.previous_state = None
        self.previous_activity = None
        self.current_print_id = None

    def handle_bambu(self):
        if not BAMBU_AUTO_FAN:
            return

        controller_state = get_state()
        mode = controller_state["control_mode"]

        if not controller_state["automation_enabled"]:
            return

        if mode == "manual" or mode == "timer":
            return

        if mode == "cooldown":
            cooldown_end = controller_state["cooldown_end"]

            if cooldown_end and time.time() >= cooldown_end:
                self.fan.turn_off("Bambu cooldown complete")
                update_state(control_mode="bambu", cooldown_end=None)

            return

        if mode != "bambu":
            return

        printer = self.bambu.get_state()
        printer_state = printer["state"]
        activity = printer["activity"]

        if activity != self.previous_activity:
            add_event("PRINTER", f"Printer activity: {activity}")
            self.previous_activity = activity

        # Start print history when a new print becomes active.
        if (
            printer_state in self.ACTIVE_STATES
            and self.previous_state not in self.ACTIVE_STATES
        ):
            self.current_print_id = start_print(
                printer.get("filename") or "Unknown print"
            )
            add_event(
                "BAMBU",
                f"Print started: {printer.get('filename') or 'Unknown print'}"
            )

        if printer_state in self.ACTIVE_STATES:
            if BAMBU_FAN_WHILE_PRINTING and not self.fan.is_on:
                self.fan.turn_on(f"Bambu: {activity}")

            self.previous_state = printer_state
            return

        error_code = printer["error_code"]

        if BAMBU_FAN_ON_ERROR and error_code is not None:
            if not self.fan.is_on:
                self.fan.turn_on("Bambu printer error")

            if self.current_print_id:
                finish_print(
                    self.current_print_id,
                    "FAILED",
                    str(error_code)
                )
                self.current_print_id = None

            self.previous_state = printer_state
            return

        if printer_state == "FINISH":
            if self.previous_state in self.ACTIVE_STATES:
                finish_print(
                    self.current_print_id,
                    "FINISH"
                )
                self.current_print_id = None

                cooldown_minutes = int(
                    controller_state["cooldown_minutes"]
                )

                cooldown_end = time.time() + cooldown_minutes * 60

                self.fan.turn_on("Print finished - cooldown")

                update_state(
                    control_mode="cooldown",
                    cooldown_end=cooldown_end,
                    timer_end=None
                )

                add_event(
                    "BAMBU",
                    f"Print finished. Cooldown {cooldown_minutes} minutes."
                )

            self.previous_state = printer_state
            return

        if printer_state == "FAILED":
            finish_print(
                self.current_print_id,
                "FAILED",
                str(error_code) if error_code is not None else "Printer reported FAILED"
            )
            self.current_print_id = None

            if BAMBU_FAN_ON_ERROR:
                self.fan.turn_on("Bambu print failed")

            self.previous_state = printer_state
            return

        if printer_state == "IDLE":
            if self.fan.is_on:
                self.fan.turn_off("Bambu idle")

        self.previous_state = printer_state

    def run(self):
        while True:
            try:
                self.timer.check()
                self.handle_bambu()
                time.sleep(1)
            except Exception as error:
                print("Automation error:", error)
                time.sleep(2)

    def start(self):
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
