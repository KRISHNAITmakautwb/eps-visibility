"""Regression tests for bugs found in review."""
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace as P
from unittest import mock

from eps_visibility.hardware import ports

FAKE_PORTS = [P(device="/dev/ttyUSB0", vid=0x0403, pid=0x6010, location="1-2:1.0"),  # FPGA JTAG
              P(device="/dev/ttyUSB1", vid=0x0403, pid=0x6010, location="1-2:1.1"),  # FPGA UART
              P(device="/dev/ttyACM0", vid=0x2341, pid=0x0043, location="1-3:1.0")]  # Arduino


class TestPortGuess(unittest.TestCase):
    def test_fpga_uart_and_arduino_are_chosen(self):
        with mock.patch.object(ports.serial.tools.list_ports, "comports", lambda: FAKE_PORTS):
            self.assertEqual(ports.detect_fpga_port(), "/dev/ttyUSB1")
            self.assertEqual(ports.guess_stage_port(), "/dev/ttyACM0")   # never the JTAG channel


@unittest.skipUnless(os.name == "posix", "resource-tracker unlink only happens on POSIX")
class TestSharedMemoryConsumer(unittest.TestCase):
    def test_attaching_does_not_destroy_producers_segment(self):
        from multiprocessing import shared_memory
        name = f"eps_test_{os.getpid()}"
        shm = shared_memory.SharedMemory(name=name, create=True, size=88)
        try:
            code = ("from eps_visibility.hardware.counts import _attach_shared_memory as a;"
                    f"m = a('{name}'); m.close()")
            subprocess.run([sys.executable, "-c", code], check=True, capture_output=True,
                           cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            shared_memory.SharedMemory(name=name).close()   # raises if the consumer unlinked it
        finally:
            shm.close()
            shm.unlink()


if __name__ == "__main__":
    unittest.main()
