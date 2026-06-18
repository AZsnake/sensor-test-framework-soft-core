"""Light/dark theme tokens and QSS for the MIPI tools GUI."""

THEME_LIGHT = {
    "plot_bg": "#f3f4f6",
    "fg": "#1a1d24",
    "fg_secondary": "#3d4450",
    "fg_muted": "#5f6773",
    "metric": "#0b4f8a",
    "border": "#c8ced6",
    "input_bg": "#fcfcfd",
    "btn_bg": "#dce1e8",
    "btn_hover": "#cfd6e0",
    "btn_pressed": "#bcc4d0",
    "highlight": "#2563eb",
}

THEME_DARK = {
    "plot_bg": "#1e1e1e",
    "fg": "#e4e4e7",
    "fg_secondary": "#c4c4cc",
    "fg_muted": "#9ca3af",
    "metric": "#60a5fa",
    "border": "#4b5563",
    "input_bg": "#262626",
    "btn_bg": "#3a3a3a",
    "btn_hover": "#454545",
    "btn_pressed": "#525252",
    "highlight": "#3b82f6",
}


def app_stylesheet(theme: dict[str, str]) -> str:
    t = theme
    return f"""
QWidget {{
    color: {t["fg"]};
}}
QMainWindow, QDialog {{
    background: {t["plot_bg"]};
}}
QGroupBox {{
    border: 1px solid {t["border"]};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: 600;
    color: {t["fg_secondary"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}}
QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {{
    background: {t["input_bg"]};
    border: 1px solid {t["border"]};
    border-radius: 3px;
    padding: 2px 4px;
    color: {t["fg"]};
}}
QPushButton {{
    background: {t["btn_bg"]};
    border: 1px solid {t["border"]};
    border-radius: 4px;
    padding: 4px 10px;
    color: {t["fg"]};
}}
QPushButton:hover {{
    background: {t["btn_hover"]};
}}
QPushButton:pressed {{
    background: {t["btn_pressed"]};
}}
QPushButton:disabled {{
    color: {t["fg_muted"]};
}}
QProgressBar {{
    border: 1px solid {t["border"]};
    border-radius: 3px;
    text-align: center;
    background: {t["input_bg"]};
}}
QProgressBar::chunk {{
    background: {t["highlight"]};
}}
"""
