"""Serial-port discovery."""
import serial.tools.list_ports

from ..config import FT2232_PID, FTDI_VID


def list_serial_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def _fpga_ports():
    return [p for p in serial.tools.list_ports.comports()
            if p.vid == FTDI_VID and p.pid == FT2232_PID]


def detect_fpga_port():
    """Digilent FT2232H: channel B (interface .1) is the FPGA UART. None if not plugged in."""
    ports = _fpga_ports()
    if not ports:
        return None
    return max(ports, key=lambda p: (1 if (p.location or "").endswith(".1") else 0, p.device)).device


def guess_stage_port():
    """First serial port that is not part of the FPGA board (both its JTAG and UART channels)."""
    fpga = {p.device for p in _fpga_ports()}
    others = [d for d in list_serial_ports() if d not in fpga]
    return others[0] if others else None
