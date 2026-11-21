"""Arduino rotation stage (same protocol as V2/TKinter_Rot_Stage.py)."""
import threading
import time

import serial

from ..config import STAGE_BAUD


def stage_command(angle, direction, mode, stage):
    """'<angle>A<Clock|AntiClock>B<Step|Home>D<M1..M4>\\n'"""
    return f"{angle:g}A{direction}B{mode}D{stage}\n"


def parse_stage_reply(msg):
    """'CUR:12;FINAL:90' -> {'CUR': '12', 'FINAL': '90'}"""
    return dict(item.split(":", 1) for item in msg.split(";") if ":" in item)


class Stage:
    def __init__(self, log, reply_cb):
        self.log, self.reply_cb = log, reply_cb
        self.ser = None
        self.lock = threading.Lock()

    @property
    def connected(self):
        return self.ser is not None and self.ser.is_open

    def open(self, port):
        self.ser = serial.Serial(port, STAGE_BAUD, timeout=0.2)
        time.sleep(2.0)        # opening the port resets the Arduino
        end = time.monotonic() + 1.0
        while time.monotonic() < end:
            line = self.ser.readline()
            if line:
                self._reply(line)

    def close(self):
        if self.ser is not None:
            try:
                self.ser.close()
            finally:
                self.ser = None

    def _reply(self, raw):
        msg = raw.decode("utf-8", errors="ignore").strip()
        if msg:
            self.reply_cb(msg)
        return msg

    def move(self, angle, direction, mode, stage, timeout=20.0, abort=None):
        """Send one command and wait for the Arduino's reply line (returns it, or None on timeout)."""
        if not self.connected:
            raise RuntimeError("rotation stage is not connected")
        cmd = stage_command(angle, direction, mode, stage)
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(cmd.encode("utf-8"))
            self.log(f"Stage <- {cmd.strip()}")
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                if abort is not None and abort.is_set():
                    return None
                line = self.ser.readline()
                if line:
                    msg = self._reply(line)
                    if msg:
                        return msg
        self.log(f"Stage: no reply within {timeout:g} s (continuing)")
        return None
