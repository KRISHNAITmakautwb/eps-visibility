"""Entry point:  python -m eps_visibility [--sim]"""
import os
import sys


def main(argv=None):
    argv = sys.argv if argv is None else argv
    # On GNOME Wayland, run through XWayland so the window keeps its normal title bar.
    if (sys.platform.startswith("linux") and os.environ.get("XDG_SESSION_TYPE") == "wayland"
            and os.environ.get("DISPLAY") and "QT_QPA_PLATFORM" not in os.environ):
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    from PyQt6.QtWidgets import QApplication
    from .gui import EpsVisibilityApp

    app = QApplication(argv)
    win = EpsVisibilityApp()
    if "--sim" in argv:
        win.sim_cb.setChecked(True)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
