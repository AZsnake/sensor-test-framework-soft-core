"""Real-time link status display."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QGroupBox, QLabel, QVBoxLayout, QWidget


class StatusDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        group = QGroupBox("链路状态")
        grid = QGridLayout(group)

        labels = ["端口", "速率 (Mbps)", "ECC 错误", "CRC 错误", "链路"]
        self._values: dict[str, QLabel] = {}
        for i, name in enumerate(labels):
            grid.addWidget(QLabel(f"{name}:"), i, 0)
            val = QLabel("--")
            val.setAlignment(Qt.AlignRight)
            grid.addWidget(val, i, 1)
            self._values[name] = val

        layout.addWidget(group)

    def update_status(self, status: dict) -> None:
        port_names = ["MIPI0", "MIPI1", "MIPI2", "MIPI3"]
        port_idx = status.get('port', 0)
        self._values["端口"].setText(
            port_names[port_idx] if 0 <= port_idx < len(port_names) else str(port_idx))
        self._values["速率 (Mbps)"].setText(str(status.get('rate_mbps', '--')))
        self._values["ECC 错误"].setText(str(status.get('ecc_err', '--')))
        self._values["CRC 错误"].setText(str(status.get('crc_err', '--')))
        link_up = status.get('link_up', False)
        link_text = "已建立" if link_up else "未建立"
        self._values["链路"].setText(link_text)
        self._values["链路"].setStyleSheet(
            "color: green" if link_up else "color: red")

    def clear(self) -> None:
        for val in self._values.values():
            val.setText("--")
            val.setStyleSheet("")
