"""MIPI VU13P Camera Validation Platform — PySide6 GUI entry point."""
from __future__ import annotations

import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                                QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                                QSplitter, QVBoxLayout, QWidget)

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))
if str(_TOOLS_DIR / "lib") not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR / "lib"))

import _bootstrap  # noqa: E402, F401

from gui.control_panel import ControlPanel  # noqa: E402
from gui.image_viewport import ImageViewport  # noqa: E402
from gui.status_dashboard import StatusDashboard  # noqa: E402
from gui.theme import THEME_DARK, THEME_LIGHT, app_stylesheet  # noqa: E402
from serial_mgr import SerialManager  # noqa: E402

APP_TITLE = "MIPI VU13P 相机验证平台"


def _default_app_font() -> QFont:
    available = {f.casefold(): f for f in QFontDatabase.families()}
    preferred = [
        "Microsoft YaHei UI", "Microsoft YaHei",
        "PingFang SC", "Hiragino Sans GB",
        "Noto Sans CJK SC", "Noto Sans SC",
        "WenQuanYi Micro Hei", "Sans Serif",
    ]
    for name in preferred:
        hit = available.get(name.casefold())
        if hit:
            return QFont(hit, 10)
    return QFont("Sans Serif", 10)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(1200, 760)

        self.mgr = SerialManager()
        self._worker: threading.Thread | None = None
        self._msg_q: queue.Queue[tuple[str, object]] = queue.Queue()
        self._dark = False
        self._theme = THEME_LIGHT
        self._status_timer = QTimer(self)

        self._build_ui()
        self._wire_signals()
        self._apply_theme(self._dark)
        self._refresh_ports()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_queue)
        self._poll_timer.start(40)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.status_label = QLabel("未连接")
        top.addWidget(self.status_label)
        top.addStretch(1)
        self.btn_theme = QPushButton("暗黑模式")
        self.btn_theme.setCheckable(True)
        self.btn_theme.clicked.connect(self._toggle_theme)
        top.addWidget(self.btn_theme)
        root.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        self.control = ControlPanel()
        self.status = StatusDashboard()
        left_lay.addWidget(self.control)
        left_lay.addWidget(self.status)
        left_lay.addStretch(1)

        self.viewport = ImageViewport()
        splitter.addWidget(left)
        splitter.addWidget(self.viewport)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, stretch=1)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        self.log_view.setFont(QFont("Consolas", 9))
        root.addWidget(self.log_view)

    def _wire_signals(self) -> None:
        cp = self.control
        cp.refresh_ports_requested.connect(self._refresh_ports)
        cp.connect_requested.connect(self._connect)
        cp.disconnect_requested.connect(self._disconnect)
        cp.status_requested.connect(self._read_status_async)
        cp.capture_requested.connect(self._capture_async)
        cp.lane_diag_requested.connect(self._lane_diag_async)
        cp.dphy_diag_requested.connect(self._dphy_diag_async)
        cp.hs_settle_sweep_requested.connect(self._hs_settle_sweep_async)
        cp.clear_errors_requested.connect(self._clear_errors_async)
        cp.apply_mipi_requested.connect(self._apply_mipi_async)
        cp.gpio_requested.connect(self._gpio_async)
        cp.read_reg_requested.connect(self._read_reg_async)
        cp.write_reg_requested.connect(self._write_reg_async)
        self.viewport.btn_save_png.clicked.connect(self._save_png)
        self.viewport.btn_save_raw.clicked.connect(self._save_raw)

        self._status_timer.timeout.connect(lambda: self._read_status_async(silent=True))

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    def _apply_theme(self, dark: bool) -> None:
        self._dark = dark
        self._theme = THEME_DARK if dark else THEME_LIGHT
        self.setStyleSheet(app_stylesheet(self._theme))
        self.btn_theme.setText("白昼模式" if dark else "暗黑模式")
        self.btn_theme.setChecked(dark)

    def _toggle_theme(self) -> None:
        self._apply_theme(self.btn_theme.isChecked())

    def _refresh_ports(self) -> None:
        ports = SerialManager.list_ports()
        self.control.set_ports(ports)
        if ports:
            self._log(f"发现 {len(ports)} 个串口")
        else:
            self._log("未发现 CH9114/USB 串口")

    def _connect(self, port: str) -> None:
        if self._worker and self._worker.is_alive():
            QMessageBox.information(self, APP_TITLE, "请等待当前操作完成")
            return
        try:
            self.mgr.connect(port)
        except Exception as e:
            QMessageBox.critical(self, APP_TITLE, f"连接失败: {e}")
            self._log(f"连接失败 {port}: {e}")
            return
        self.control.set_connected(True)
        self.status_label.setText(f"已连接 {port}")
        self._log(f"已连接 {port} @ {SerialManager.BAUD}")
        self._status_timer.start(2000)

    def _disconnect(self) -> None:
        if self._worker and self._worker.is_alive():
            QMessageBox.information(self, APP_TITLE, "请等待当前操作完成")
            return
        self._status_timer.stop()
        self.mgr.disconnect()
        self.control.set_connected(False)
        self.status.clear()
        self.status_label.setText("未连接")
        self._log("已断开")

    def _run_async(self, label: str, fn) -> None:
        if not self.mgr.connected:
            QMessageBox.warning(self, APP_TITLE, "请先连接串口")
            return
        if self._worker and self._worker.is_alive():
            QMessageBox.information(self, APP_TITLE, "上一操作仍在进行，请稍候")
            return

        self.control.set_busy(True)
        self.status_label.setText(f"进行中: {label}...")

        def target() -> None:
            try:
                fn()
                self._msg_q.put(("done", label))
            except Exception as e:
                self._msg_q.put(("error", str(e)))

        self._worker = threading.Thread(target=target, daemon=True)
        self._worker.start()

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._msg_q.get_nowait()
                if kind == "done":
                    self.status_label.setText(f"完成: {payload}")
                    self.control.set_busy(False)
                    self.control.hide_progress()
                elif kind == "error":
                    self.status_label.setText("错误")
                    self.control.set_busy(False)
                    self.control.hide_progress()
                    self._log(f"错误: {payload}")
                    QMessageBox.critical(self, APP_TITLE, str(payload))
                elif kind == "log":
                    self._log(str(payload))
                elif kind == "progress":
                    cur, tot = payload  # type: ignore[misc]
                    self.control.show_progress(int(tot), int(cur))
                elif kind == "status":
                    self.status.update_status(payload)  # type: ignore[arg-type]
                elif kind == "reg_data":
                    self.control.set_reg_data(int(payload))  # type: ignore[arg-type]
                elif kind == "image":
                    data, w, h, elapsed = payload  # type: ignore[misc]
                    self.viewport.display_raw10(data, w, h, elapsed)
                    self._log(f"抓图完成: {w}×{h}, {len(data)} B, {elapsed:.1f}s")
        except queue.Empty:
            pass

    def _read_status_async(self, *, silent: bool = False) -> None:
        def job():
            status = self.mgr.read_status()
            self._msg_q.put(("status", status))
            if not silent:
                self._msg_q.put(("log",
                                 f"状态: LinkUp={status['link_up']} "
                                 f"Rate={status['rate_mbps']}Mbps "
                                 f"ECC={status['ecc_err']} CRC={status['crc_err']}"))

        if silent:
            if not self.mgr.connected or (self._worker and self._worker.is_alive()):
                return

            def target() -> None:
                try:
                    job()
                except Exception:
                    pass

            threading.Thread(target=target, daemon=True).start()
            return
        self._run_async("读状态", job)

    def _capture_async(self, width: int, height: int) -> None:
        total = width * height * 10 // 8

        def job():
            self._msg_q.put(("progress", (0, total)))
            self._msg_q.put(("log", f"抓图开始: {width}×{height} ({total} B)..."))
            t0 = time.perf_counter()

            def on_progress(received: int, expected: int) -> None:
                self._msg_q.put(("progress", (received, expected)))

            data = self.mgr.capture_image(width, height, progress_cb=on_progress)
            elapsed = time.perf_counter() - t0
            if data:
                self._msg_q.put(("image", (data, width, height, elapsed)))
            else:
                raise RuntimeError("抓图超时或数据不完整")

        self._run_async("抓图", job)

    def _lane_diag_async(self) -> None:
        def job():
            d = self.mgr.lane_diag()
            f = d['flags']
            self._msg_q.put(("log",
                "Lane 诊断: "
                f"CCR=0x{d['CCR']:08X} CSR=0x{d['CSR']:08X} ISR=0x{d['ISR']:08X} "
                f"CLK=0x{d['CLK_LANE']:08X} L0=0x{d['LANE0']:08X} L1=0x{d['LANE1']:08X}"))
            self._msg_q.put(("log",
                f"  判读: pkt_count={f['pkt_count']}  "
                f"CLK_lane {'Stop(未进HS)' if f['clk_stop'] else 'HS✓'}"))
            self._msg_q.put(("log",
                f"  Lane0: stop={int(f['l0_stop'])} SoTErr={int(f['l0_sot_err'])} "
                f"SoTSyncErr={int(f['l0_sotsync_err'])}   "
                f"Lane1: stop={int(f['l1_stop'])} SoTErr={int(f['l1_sot_err'])} "
                f"SoTSyncErr={int(f['l1_sotsync_err'])}"))
        self._run_async("Lane 诊断", job)

    def _dphy_diag_async(self) -> None:
        def job():
            d = self.mgr.dphy_diag()
            f = d['flags']
            self._msg_q.put(("log",
                "D-PHY 诊断: "
                f"CTRL=0x{d['CTRL']:08X} CLSTATUS=0x{d['CLSTATUS']:08X} "
                f"DL0=0x{d['DL0STATUS']:08X} DL1=0x{d['DL1STATUS']:08X} "
                f"HS_SETTLE L0={d['HSSETTLE_L0']} L1={d['HSSETTLE_L1']}"))
            c = f['clk']
            self._msg_q.put(("log",
                f"  CLK lane: Mode={c['mode']} InitDone={int(c['init_done'])} "
                f"Stop={int(c['stop'])} ErrCtrl={int(c['err_ctrl'])} "
                f"(DphyEn={int(f['dphy_en'])})"))
            for name in ('dl0', 'dl1'):
                L = f[name]
                self._msg_q.put(("log",
                    f"  {name.upper()}: Mode={L['mode']} InitDone={int(L['init_done'])} "
                    f"Calib={int(L['calib_complete'])} HSAbort={int(L['hs_abort'])} "
                    f"Stop={int(L['stop'])} pkt={L['pkt_count']}"))
        self._run_async("D-PHY 诊断", job)

    def _hs_settle_sweep_async(self) -> None:
        def job():
            self._msg_q.put(("log", "HS_SETTLE 扫描开始 (sensor 须在出流)..."))
            self.mgr.sweep_hs_settle(log=lambda m: self._msg_q.put(("log", m)))
        self._run_async("扫描 HS_SETTLE", job)

    def _clear_errors_async(self) -> None:
        def job():
            self.mgr.clear_errors()
            self._msg_q.put(("log", "误码计数已清零 (0x0A)"))
        self._run_async("清误码", job)

    def _apply_mipi_async(self, port: int, source: int) -> None:
        def job():
            self.mgr.set_port(port)
            self.mgr.set_source(source)
            self._msg_q.put(("log", f"MIPI 配置: Port={port}, Source={source}"))
        self._run_async("应用 MIPI", job)

    def _gpio_async(self, pin: int, level: int) -> None:
        pin_names = {0: "RESET", 1: "PWDN"}

        def job():
            self.mgr.gpio_ctrl(pin, level)
            self._msg_q.put(("log", f"GPIO {pin_names.get(pin, pin)} = {level}"))
        self._run_async("GPIO", job)

    def _read_reg_async(self, addr: int) -> None:
        def job():
            val = self.mgr.read_reg(addr)
            self._msg_q.put(("reg_data", val))
            self._msg_q.put(("log", f"读寄存器 0x{addr:04X} = 0x{val:02X}"))
        self._run_async("读寄存器", job)

    def _write_reg_async(self, addr: int, data: int) -> None:
        def job():
            self.mgr.write_reg(addr, data)
            self._msg_q.put(("log", f"写寄存器 0x{addr:04X} = 0x{data:02X}"))
        self._run_async("写寄存器", job)

    def _save_png(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 PNG", f"capture_{ts}.png", "PNG (*.png);;All (*.*)")
        if path and self.viewport.save_png(path):
            self._log(f"已保存 PNG: {path}")

    def _save_raw(self) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 RAW", f"capture_{ts}.raw", "RAW (*.raw);;All (*.*)")
        if path and self.viewport.save_raw(path):
            self._log(f"已保存 RAW: {path}")

    def closeEvent(self, event):
        self._status_timer.stop()
        if self.mgr.connected:
            self.mgr.disconnect()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    app.setFont(_default_app_font())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
