"""Colour theme: one palette used by the Qt widgets and the matplotlib plot."""

C = dict(
    bg="#eef2f7",          # window background
    panel="#ffffff",       # group boxes, log, plot
    border="#d3dbe6",
    text="#1f2a37",
    muted="#64748b",
    accent="#2563eb",      # blue: headings, focus, singles Ch 1
    accent2="#0891b2",     # teal: singles Ch 2
    coinc="#ea580c",       # orange: coincidences
    fit="#334155",
    ok="#16a34a",          # green: start / running
    ok_hover="#15803d",
    bad="#dc2626",         # red: stop
    bad_hover="#b91c1c",
    idle="#94a3b8",        # grey status light
    result_bg="#ecfdf5",
    result_fg="#065f46",
    log_bg="#0f172a",
    log_fg="#cbd5e1",
)

QSS = f"""
QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {C['bg']}; }}
QWidget {{ color: {C['text']}; font-size: 13px; }}

QGroupBox {{
    background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 8px;
    margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 6px;
    color: {C['accent']}; background: transparent;
}}

QPushButton {{
    background: #e8eefc; color: #1e3a8a; border: 1px solid #7c9be6; border-radius: 6px;
    padding: 6px 14px; font-weight: 600; min-height: 20px;
}}
QPushButton:hover {{ background: #d6e1fb; border-color: {C['accent']}; }}
QPushButton:pressed {{ background: #c3d3f8; }}
QPushButton:disabled {{ background: #e5e7eb; color: #6b7280; border: 1px solid #c4c9d2; }}
QPushButton[role="go"] {{
    background: {C['ok']}; color: white; border: 1px solid #15803d; font-weight: 700;
    padding: 8px 16px; font-size: 14px;
}}
QPushButton[role="go"]:hover {{ background: {C['ok_hover']}; color: white; }}
QPushButton[role="stop"] {{
    background: {C['bad']}; color: white; border: 1px solid #b91c1c; font-weight: 700;
    padding: 8px 16px; font-size: 14px;
}}
QPushButton[role="stop"]:hover {{ background: {C['bad_hover']}; color: white; }}
QPushButton[role="go"]:disabled, QPushButton[role="stop"]:disabled {{
    background: #9ca3af; color: white; border: 1px solid #8b929c;
}}
QWidget#actionBar {{ background: {C['panel']}; border-top: 1px solid {C['border']}; }}

QComboBox, QSpinBox, QDoubleSpinBox {{
    background: white; border: 1px solid {C['border']}; border-radius: 5px; padding: 3px 6px;
}}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {C['accent']}; }}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ background: #f1f5f9; color: #6b7280; }}

/* the list that opens under a dropdown: light, with a blue highlight.
   The frame around it is painted too: on GNOME/XWayland an unpainted popup frame shows black. */
QComboBox {{ combobox-popup: 0; }}
QComboBoxPrivateContainer, QComboBox QFrame {{
    background: white; border: 1px solid {C['border']}; border-radius: 4px;
}}
QComboBox QAbstractItemView {{
    background: white; color: {C['text']}; border: 1px solid {C['border']};
    selection-background-color: #dbe6fd; selection-color: #1e3a8a; outline: 0; padding: 2px;
}}
QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 2px 8px; }}
QComboBox QAbstractItemView::item:hover {{ background: #eef3fe; }}

QToolTip {{ background: #1f2a37; color: white; border: none; padding: 5px 8px; }}
QMenu {{ background: white; color: {C['text']}; border: 1px solid {C['border']}; }}
QMenu::item:selected {{ background: #dbe6fd; color: #1e3a8a; }}
QMessageBox, QFileDialog {{ background: {C['panel']}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}

QLabel[role="count-single"] {{ color: {C['accent']}; font-family: monospace; font-weight: 700; font-size: 14px; }}
QLabel[role="count-coinc"]  {{ color: {C['coinc']};  font-family: monospace; font-weight: 700; font-size: 14px; }}
QLabel[role="muted"] {{ color: {C['muted']}; }}
QLabel[role="result"] {{
    background: {C['result_bg']}; color: {C['result_fg']}; border: 1px solid #a7f3d0;
    border-radius: 8px; padding: 8px 12px; font-size: 17px; font-weight: 700;
}}
QLabel[role="result-empty"] {{
    background: {C['panel']}; color: {C['muted']}; border: 1px solid {C['border']};
    border-radius: 8px; padding: 8px 12px; font-size: 17px; font-weight: 700;
}}

QLabel[role="sim-banner"] {{
    background: {C['bad']}; color: white; border-radius: 8px; padding: 8px 12px;
    font-size: 16px; font-weight: 800; letter-spacing: 1px;
}}

QTextEdit {{
    background: {C['log_bg']}; color: {C['log_fg']}; border-radius: 8px; border: none;
    font-family: monospace; font-size: 12px; padding: 6px;
}}
QSplitter::handle {{ background: {C['bg']}; width: 6px; }}
"""


def apply_theme(app):
    """Light look regardless of the desktop's dark mode (e.g. Ubuntu Yaru-dark).

    The stylesheet only covers what it names; everything else (dropdown lists, dialogs, menus,
    scrollbars) takes the palette, which Qt otherwise copies from the dark system theme.
    """
    from PyQt6.QtGui import QColor, QPalette
    app.setStyle("Fusion")
    pal = QPalette()
    roles = QPalette.ColorRole
    for role, colour in ((roles.Window, C["bg"]), (roles.WindowText, C["text"]),
                         (roles.Base, "#ffffff"), (roles.AlternateBase, "#f5f7fb"),
                         (roles.Text, C["text"]), (roles.Button, "#e8eefc"),
                         (roles.ButtonText, "#1e3a8a"), (roles.ToolTipBase, "#1f2a37"),
                         (roles.ToolTipText, "#ffffff"), (roles.Highlight, "#dbe6fd"),
                         (roles.HighlightedText, "#1e3a8a"), (roles.PlaceholderText, C["muted"]),
                         (roles.Link, C["accent"])):
        pal.setColor(role, QColor(colour))
    for role in (roles.WindowText, roles.Text, roles.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor("#6b7280"))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


def status_dot(color):
    return (f"background: {color}; border-radius: 6px; min-width: 12px; max-width: 12px; "
            f"min-height: 12px; max-height: 12px;")


def set_role(widget, role):
    """Change a widget's QSS role and re-apply the style."""
    if widget.property("role") != role:
        widget.setProperty("role", role)
        widget.style().unpolish(widget)
        widget.style().polish(widget)


def style_axes(fig, axes):
    fig.set_facecolor(C["panel"])
    for ax in axes:
        ax.set_facecolor(C["panel"])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(C["border"])
        ax.tick_params(colors=C["muted"])
        ax.yaxis.label.set_color(C["text"])
        ax.xaxis.label.set_color(C["text"])
        ax.grid(color=C["border"], alpha=0.7, lw=0.8)
