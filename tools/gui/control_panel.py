"""Port selection, sensor control, and capture parameters."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QGroupBox, QHBoxLayout, QLabel,
                                QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
                                QWidget)

# Sensor 输出 2016 宽 (IMX298 当前 2016×1512 基线, X_OUT=2016, RAW10)。抓图宽度必须
# = 真实行宽, 否则行 stride 不匹配 → 图像水平错位。高度可截断(只取前 N 行)控传输时长。
# 230400 baud ≈ 23 KB/s, 2016×1512 ≈ 3.8 MB ≈ 165s。
RESOLUTION_PRESETS: list[tuple[str, int, int]] = [
    ("2016×128 (快速条带)", 2016, 128),
    ("2016×512", 2016, 512),
    ("2016×1512 (全幅, ~3min)", 2016, 1512),
]


class ControlPanel(QWidget):
    status_requested = Signal()
    capture_requested = Signal(int, int)
    lane_diag_requested = Signal()
    dphy_diag_requested = Signal()
    hs_settle_sweep_requested = Signal()
    clear_errors_requested = Signal()
    apply_mipi_requested = Signal(int, int)
    gpio_requested = Signal(int, int)
    read_reg_requested = Signal(int)
    write_reg_requested = Signal(int, int)
    connect_requested = Signal(str)
    disconnect_requested = Signal()
    refresh_ports_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._setup_ui()
        self.set_connected(False)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        conn_group = QGroupBox("串口连接")
        conn_lay = QHBoxLayout(conn_group)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(180)
        self.btn_refresh = QPushButton("刷新")
        self.btn_connect = QPushButton("连接")
        conn_lay.addWidget(QLabel("端口:"))
        conn_lay.addWidget(self.port_combo)
        conn_lay.addWidget(self.btn_refresh)
        conn_lay.addWidget(self.btn_connect)
        layout.addWidget(conn_group)

        mipi_group = QGroupBox("MIPI 控制 (VU13P 单相机)")
        mipi_lay = QHBoxLayout(mipi_group)
        self.port_sel = QComboBox()
        self.port_sel.addItems(["MIPI0"])
        self.port_sel.setCurrentIndex(0)
        self.port_sel.setToolTip("VU13P 仅单 RX；固定 MIPI0 (0x08 协议兼容)")
        self.source_sel = QComboBox()
        self.source_sel.addItems(["摄像头"])
        self.source_sel.setCurrentIndex(0)
        self.source_sel.setToolTip("VU13P 仅支持摄像头模式 (Source=0)")
        self.btn_apply = QPushButton("应用")
        mipi_lay.addWidget(QLabel("端口:"))
        mipi_lay.addWidget(self.port_sel)
        mipi_lay.addWidget(QLabel("模式:"))
        mipi_lay.addWidget(self.source_sel)
        mipi_lay.addWidget(self.btn_apply)
        layout.addWidget(mipi_group)

        cap_group = QGroupBox("抓图参数")
        cap_lay = QHBoxLayout(cap_group)
        self.res_combo = QComboBox()
        for label, _, _ in RESOLUTION_PRESETS:
            self.res_combo.addItem(label)
        cap_lay.addWidget(QLabel("分辨率:"))
        cap_lay.addWidget(self.res_combo)
        cap_lay.addStretch(1)
        layout.addWidget(cap_group)

        # Sensor 由固件 boot 自动初始化并出流 (复位+1076条init表+stream-on),
        # 固件无"重新init"命令; GUI 只暴露观测/采集动作, 不提供会让 sensor 掉流的复位/init。
        sensor_group = QGroupBox("Sensor 控制 (boot 自动初始化)")
        sensor_lay = QHBoxLayout(sensor_group)
        self.btn_status = QPushButton("读状态 (0x03)")
        self.btn_capture = QPushButton("抓图 (0x04)")
        self.btn_lane_diag = QPushButton("Lane 诊断 (0x0B)")
        self.btn_lane_diag.setToolTip("读 CSI-2 RX 子系统 lane 状态寄存器, 定位哪条 lane 不同步")
        self.btn_dphy_diag = QPushButton("D-PHY 诊断 (0x0D)")
        self.btn_dphy_diag.setToolTip(
            "读 D-PHY 子块状态: 每 lane Mode/InitDone/CalibComplete/HSAbort/Stop "
            "+ per-lane 包计数。比 Lane 诊断(0x0B)更深, 区分时钟侧/数据侧故障。\n"
            "需 bit流 DPY_EN_REG_IF=true。")
        self.btn_hs_sweep = QPushButton("扫 HS_SETTLE (0x0C)")
        self.btn_hs_sweep.setToolTip(
            "在线扫描 D-PHY HS_SETTLE 采样窗口, 找出能干净解包的值。\n"
            "前提: 固件含 0x0C、bit流 DPY_EN_REG_IF=true、sensor 正在出流。\n"
            "耗时约 10~20s, 结果打到日志区。")
        self.btn_clear_err = QPushButton("清误码 (0x0A)")
        sensor_lay.addWidget(self.btn_status)
        sensor_lay.addWidget(self.btn_capture)
        sensor_lay.addWidget(self.btn_lane_diag)
        sensor_lay.addWidget(self.btn_dphy_diag)
        sensor_lay.addWidget(self.btn_hs_sweep)
        sensor_lay.addWidget(self.btn_clear_err)
        sensor_lay.addStretch(1)
        layout.addWidget(sensor_group)

        gpio_group = QGroupBox("GPIO (RESET / PWDN)")
        gpio_lay = QHBoxLayout(gpio_group)
        self.btn_reset_high = QPushButton("RESET 高")
        self.btn_reset_low = QPushButton("RESET 低")
        self.btn_pwdn_high = QPushButton("PWDN 高")
        self.btn_pwdn_low = QPushButton("PWDN 低")
        gpio_lay.addWidget(self.btn_reset_high)
        gpio_lay.addWidget(self.btn_reset_low)
        gpio_lay.addWidget(self.btn_pwdn_high)
        gpio_lay.addWidget(self.btn_pwdn_low)
        layout.addWidget(gpio_group)

        reg_group = QGroupBox("寄存器调试")
        reg_lay = QHBoxLayout(reg_group)
        reg_lay.addWidget(QLabel("地址"))
        self.reg_addr_edit = QLineEdit("0x0016")
        self.reg_addr_edit.setFixedWidth(78)
        reg_lay.addWidget(self.reg_addr_edit)
        reg_lay.addWidget(QLabel("数值"))
        self.reg_data_edit = QLineEdit("0x00")
        self.reg_data_edit.setFixedWidth(78)
        reg_lay.addWidget(self.reg_data_edit)
        self.btn_read_reg = QPushButton("读 (0x02)")
        self.btn_write_reg = QPushButton("写 (0x01)")
        reg_lay.addWidget(self.btn_read_reg)
        reg_lay.addWidget(self.btn_write_reg)
        layout.addWidget(reg_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        layout.addStretch(1)

        self.btn_refresh.clicked.connect(self.refresh_ports_requested.emit)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_apply.clicked.connect(self._on_apply_mipi)
        self.btn_status.clicked.connect(self.status_requested.emit)
        self.btn_lane_diag.clicked.connect(self.lane_diag_requested.emit)
        self.btn_dphy_diag.clicked.connect(self.dphy_diag_requested.emit)
        self.btn_hs_sweep.clicked.connect(self.hs_settle_sweep_requested.emit)
        self.btn_capture.clicked.connect(self._on_capture)
        self.btn_clear_err.clicked.connect(self.clear_errors_requested.emit)
        self.btn_reset_high.clicked.connect(lambda: self.gpio_requested.emit(0, 1))
        self.btn_reset_low.clicked.connect(lambda: self.gpio_requested.emit(0, 0))
        self.btn_pwdn_high.clicked.connect(lambda: self.gpio_requested.emit(1, 1))
        self.btn_pwdn_low.clicked.connect(lambda: self.gpio_requested.emit(1, 0))
        self.btn_read_reg.clicked.connect(self._on_read_reg)
        self.btn_write_reg.clicked.connect(self._on_write_reg)

    def _action_widgets(self) -> list[QWidget]:
        return [
            self.btn_apply, self.btn_status, self.btn_lane_diag, self.btn_dphy_diag,
            self.btn_hs_sweep, self.btn_capture, self.btn_clear_err,
            self.btn_reset_high, self.btn_reset_low, self.btn_pwdn_high, self.btn_pwdn_low,
            self.btn_read_reg, self.btn_write_reg,
        ]

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self.btn_connect.setText("断开" if connected else "连接")
        self.port_combo.setEnabled(not connected)
        for w in self._action_widgets():
            w.setEnabled(connected)

    def set_busy(self, busy: bool) -> None:
        for w in self._action_widgets():
            w.setEnabled(not busy and self._connected)
        self.btn_connect.setEnabled(not busy)
        self.btn_refresh.setEnabled(not busy and not self._connected)

    def set_ports(self, ports: list[str]) -> None:
        prev = self.port_combo.currentText()
        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if prev in ports:
            self.port_combo.setCurrentText(prev)
        elif ports:
            self.port_combo.setCurrentIndex(0)
        self.port_combo.blockSignals(False)

    def resolution(self) -> tuple[int, int]:
        idx = self.res_combo.currentIndex()
        if 0 <= idx < len(RESOLUTION_PRESETS):
            _, w, h = RESOLUTION_PRESETS[idx]
            return w, h
        return 640, 480

    def show_progress(self, maximum: int, value: int = 0) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def hide_progress(self) -> None:
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)

    def update_progress(self, value: int, maximum: int | None = None) -> None:
        if maximum is not None:
            self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(value)

    def _on_connect_clicked(self) -> None:
        if self._connected:
            self.disconnect_requested.emit()
        else:
            port = self.port_combo.currentText()
            if port:
                self.connect_requested.emit(port)

    def _on_apply_mipi(self) -> None:
        self.apply_mipi_requested.emit(
            self.port_sel.currentIndex(),
            self.source_sel.currentIndex(),
        )

    def _on_capture(self) -> None:
        w, h = self.resolution()
        self.capture_requested.emit(w, h)

    def _parse_hex(self, text: str) -> int:
        text = text.strip()
        if text.lower().startswith('0x'):
            return int(text, 16)
        return int(text)

    def _on_read_reg(self) -> None:
        try:
            addr = self._parse_hex(self.reg_addr_edit.text())
        except ValueError:
            return
        self.read_reg_requested.emit(addr)

    def _on_write_reg(self) -> None:
        try:
            addr = self._parse_hex(self.reg_addr_edit.text())
            data = self._parse_hex(self.reg_data_edit.text())
        except ValueError:
            return
        self.write_reg_requested.emit(addr, data & 0xFF)

    def set_reg_data(self, value: int) -> None:
        self.reg_data_edit.setText(f"0x{value & 0xFF:02X}")
