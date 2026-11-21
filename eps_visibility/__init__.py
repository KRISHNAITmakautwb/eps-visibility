"""EPS Visibility: polarization-visibility scan of the entangled photon source.

Replaces V2/producer.py, REciever.py, TKinter_Rot_Stage.py and Visibility.py.

    config      constants and paths
    hardware/   FPGA count sources, Arduino stage, simulators, port discovery
    scan        the step-scan work loop (run_scan)
    analysis    raw and fitted visibility
    storage     CSV output
    gui         PyQt6 window
"""
from .config import APP_TITLE, __version__

__all__ = ["APP_TITLE", "__version__"]
