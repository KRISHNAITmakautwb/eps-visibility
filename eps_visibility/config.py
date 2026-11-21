"""Constants and paths shared by the whole application."""
import os
import sys

APP_TITLE = "EPS Visibility"
__version__ = "3.0.0"

PKG_DIR = os.path.dirname(os.path.abspath(__file__))
EPS_DIR = os.path.dirname(PKG_DIR)
QUANTUM_DIR = os.path.dirname(EPS_DIR)       # holds Qutess_1.py and source.py
DATA_DIR = os.path.join(EPS_DIR, "data")

SHM_NAME = "qutess_counts"                   # same name/layout as V2/producer.py
COUNTER_NAMES = ["ch1", "ch2", "ch3", "ch4", "c12", "c13", "c14", "c23", "c24", "c34"]
CHANNEL_LABELS = ["Ch 1", "Ch 2", "Ch 3", "Ch 4", "Coinc 1-2", "Coinc 1-3", "Coinc 1-4",
                  "Coinc 2-3", "Coinc 2-4", "Coinc 3-4"]

FTDI_VID, FT2232_PID = 0x0403, 0x6010        # Digilent on-board USB (FT2232H)
STAGE_BAUD = 9600
STAGE_IDS = ["M1", "M2", "M3", "M4"]
DIRECTIONS = ["Clock", "AntiClock"]


def ensure_qutess_on_path():
    """Make ../Qutess_1.py and ../source.py importable."""
    if QUANTUM_DIR not in sys.path:
        sys.path.insert(0, QUANTUM_DIR)
