"""Serial port manager for CH9114 UART_AP communication."""
import time
import threading
from typing import Optional, Callable

import serial
import serial.tools.list_ports

from protocol import (build_frame, parse_frame, ParsedFrame, FrameError,
                      CMD, ERR, HEADER, IMG_DATA_HEADER, IMG_EOT_HEADER,
                      parse_status, parse_lane_diag, parse_dphy_diag)


class SerialManager:
    BAUD = 230400
    CMD_TIMEOUT = 0.5
    # 抓图超时按字节数动态算 (见 capture_image): 230400 baud 8N1 ≈ 23040 B/s,
    # 协议每 512B 加 ~7B 头/校验; 取 1.6x 余量 + 3s 基底(含帧等待)。
    CAPTURE_BYTES_PER_SEC = 23040

    def __init__(self):
        self._port: Optional[serial.Serial] = None
        self._lock = threading.Lock()

    @staticmethod
    def list_ports() -> list[str]:
        return [p.device for p in serial.tools.list_ports.comports()
                if 'CH9114' in (p.description or '') or 'USB' in (p.description or '')]

    def connect(self, port_name: str) -> None:
        self._port = serial.Serial(port_name, self.BAUD, timeout=0.1)
        self._port.reset_input_buffer()

    def disconnect(self) -> None:
        if self._port and self._port.is_open:
            self._port.close()
        self._port = None

    @property
    def connected(self) -> bool:
        return self._port is not None and self._port.is_open

    def send_command(self, cmd: int, payload: bytes = b'',
                     timeout: float = CMD_TIMEOUT,
                     retry: int = 1) -> ParsedFrame:
        with self._lock:
            for attempt in range(retry + 1):
                self._port.reset_input_buffer()
                frame = build_frame(cmd, payload)
                self._port.write(frame)

                resp = self._read_response(timeout)
                if resp is not None:
                    return resp
            raise TimeoutError(f"Command 0x{cmd:02X} timed out after {retry+1} attempts")

    def _read_response(self, timeout: float) -> Optional[ParsedFrame]:
        buf = bytearray()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            chunk = self._port.read(256)
            if chunk:
                buf.extend(chunk)
                idx = buf.find(HEADER)
                if idx >= 0 and len(buf) >= idx + 6:
                    cmd = buf[idx+2]
                    length = (buf[idx+3] << 8) | buf[idx+4]
                    total = idx + 5 + length + 1
                    if len(buf) >= total:
                        try:
                            return parse_frame(bytes(buf[idx:total]))
                        except FrameError:
                            buf = buf[idx+2:]
        return None

    def write_reg(self, addr: int, data: int) -> ParsedFrame:
        payload = bytes([addr >> 8, addr & 0xFF, data])
        return self.send_command(CMD.WRITE_REG, payload)

    def read_reg(self, addr: int) -> int:
        payload = bytes([addr >> 8, addr & 0xFF])
        resp = self.send_command(CMD.READ_REG, payload)
        if resp.cmd == CMD.ERR:
            raise RuntimeError(f"Read reg error: 0x{resp.payload[0]:02X}")
        return resp.payload[0]

    def read_status(self) -> dict:
        resp = self.send_command(CMD.READ_STATUS)
        return parse_status(resp.payload)

    def lane_diag(self) -> dict:
        resp = self.send_command(CMD.LANE_DIAG)
        if resp.cmd == CMD.ERR:
            raise RuntimeError(f"Lane diag error: 0x{resp.payload[0]:02X}")
        return parse_lane_diag(resp.payload)

    def dphy_diag(self) -> dict:
        resp = self.send_command(CMD.DPHY_DIAG)
        if resp.cmd == CMD.ERR:
            raise RuntimeError(f"DPHY diag error: 0x{resp.payload[0]:02X}")
        return parse_dphy_diag(resp.payload)

    def set_hs_settle(self, value: int) -> tuple[int, int]:
        """写 D-PHY HS_SETTLE (L0/L1) 裸寄存器值; value=0xFFFF 只读回探(不写)。

        返回 (L0, L1) 回读值。需 bit流 build 时 DPY_EN_REG_IF=true, 否则回读恒 0。
        """
        payload = bytes([(value >> 8) & 0xFF, value & 0xFF])
        resp = self.send_command(CMD.SET_HS_SETTLE, payload)
        if resp.cmd == CMD.ERR:
            raise RuntimeError(f"set_hs_settle error: 0x{resp.payload[0]:02X}")
        l0 = (resp.payload[0] << 8) | resp.payload[1]
        l1 = (resp.payload[2] << 8) | resp.payload[3]
        return l0, l1

    def sweep_hs_settle(self, min_ns: float = 70.0, max_ns: float = 160.0,
                        dwell: float = 0.35, build_ns: float = 147.0,
                        log: Optional[Callable[[str], None]] = None) -> list[tuple]:
        """在线扫描 D-PHY HS_SETTLE, 找出能干净解包的采样窗口。

        判据用 pkt_count 的"增量"(Δpkt, 两次 lane_diag 之差)而非绝对值——CSR 计数
        累加, 只有增量能反映"当前这个 HS_SETTLE 正在解包"。先用 0xFFFF 回探 build
        烧入值 N0 自校准 ns/LSB=build_ns/N0, 免硬编换算系数。

        log: 可选回调, 每行进度调用一次(GUI 与 CLI 共用)。
        返回 [(reg, ns, dpkt, ecc, crc, sot), ...]; 寄存器接口未生效时返回 []。
        """
        def emit(m: str) -> None:
            if log:
                log(m)

        st = self.read_status()
        emit(f"LinkUp={st['link_up']} Rate={st['rate_mbps']}Mbps "
             f"ECC={st['ecc_err']} CRC={st['crc_err']}")
        if not st['link_up']:
            emit("⚠ LinkUp=False: 时钟 lane 未进 HS, 确认 sensor 在出流再扫")

        n0, n0_l1 = self.set_hs_settle(0xFFFF)
        emit(f"当前 HS_SETTLE 寄存器: L0={n0} L1={n0_l1} (build={build_ns:.0f}ns)")
        if n0 == 0:
            emit("✗ 回读=0: D-PHY 寄存器接口未生效(DPY_EN_REG_IF) 或地址不对; "
                 "需开寄存器接口重导 XSA/重编固件")
            return []
        ns_per_lsb = build_ns / n0
        emit(f"自校准: {ns_per_lsb:.2f} ns/LSB")

        n_min = max(1, round(min_ns / ns_per_lsb))
        n_max = min(0x1FF, round(max_ns / ns_per_lsb))
        if n_max < n_min:
            n_min, n_max = n_max, n_min
        emit(f"扫描 reg {n_min}..{n_max} "
             f"(~{n_min*ns_per_lsb:.0f}..{n_max*ns_per_lsb:.0f}ns), dwell={dwell}s")

        results: list[tuple] = []
        for n in range(n_min, n_max + 1):
            self.set_hs_settle(n)
            self.clear_errors()              # 清 ECC/CRC + ISR sticky, 反映本设定
            time.sleep(dwell)
            p0 = self.lane_diag()['flags']['pkt_count']
            time.sleep(dwell)
            d1 = self.lane_diag()['flags']
            st2 = self.read_status()
            dpkt = (d1['pkt_count'] - p0) & 0xFFFF   # 16-bit 计数回绕
            sot = int(d1['l0_sot_err'] or d1['l0_sotsync_err']
                      or d1['l1_sot_err'] or d1['l1_sotsync_err'])
            ecc, crc = st2['ecc_err'], st2['crc_err']
            if dpkt > 0 and ecc == 0 and crc == 0 and sot == 0:
                verdict = "✓ 干净解包"
            elif dpkt > 0:
                verdict = "△ 有包但有误码"
            else:
                verdict = ""
            emit(f"  reg={n:<3} ~{n*ns_per_lsb:>3.0f}ns  Δpkt={dpkt:<6} pkt={d1['pkt_count']:<6} "
                 f"ECC={ecc} CRC={crc} SoT={sot}  {verdict}")
            results.append((n, n * ns_per_lsb, dpkt, ecc, crc, sot))

        clean = [r for r in results if r[2] > 0 and r[3] == 0 and r[4] == 0 and r[5] == 0]
        if clean:
            lo = min(r[0] for r in clean)
            hi = max(r[0] for r in clean)
            mid = (lo + hi) // 2
            emit(f"✓ 干净解包窗口: reg {lo}..{hi} "
                 f"(~{lo*ns_per_lsb:.0f}..{hi*ns_per_lsb:.0f}ns); "
                 f"建议中心 reg={mid} (~{mid*ns_per_lsb:.0f}ns) 固化 C_HS_SETTLE_NS 重建")
        elif any(r[2] > 0 for r in results):
            emit("△ 有值能解包但都伴误码: 扩大范围或查信号完整性(端接/眼图)")
        else:
            emit("✗ 全区间零包: HS_SETTLE 非主因, 转查 byte-group 可达性"
                 "(CLK/D0/D1 跨 I/O 组)或数据 lane HS 是否真到接收机")
        return results

    def reset_sensor(self) -> None:
        self.send_command(CMD.RESET_SEQ)

    def set_port(self, port: int) -> None:
        self.send_command(CMD.SET_PORT, bytes([port]))

    def set_source(self, source: int) -> None:
        self.send_command(CMD.SET_SOURCE, bytes([source]))

    def clear_errors(self) -> None:
        self.send_command(CMD.CLR_ERR)

    def gpio_ctrl(self, pin: int, level: int) -> None:
        self.send_command(CMD.GPIO_CTRL, bytes([pin, level]))

    def capture_image(self, width: int = 640, height: int = 480,
                      progress_cb: Optional[Callable[[int, int], None]] = None
                      ) -> Optional[bytes]:
        total_bytes = width * height * 10 // 8
        timeout = max(3.0, total_bytes / self.CAPTURE_BYTES_PER_SEC * 1.6 + 3.0)
        port_val = 0  # current port, ignored by firmware in this version
        payload = bytes([port_val, width >> 8, width & 0xFF,
                         height >> 8, height & 0xFF])

        with self._lock:
            self._port.reset_input_buffer()
            self._port.write(build_frame(CMD.CAPTURE, payload))

            # Wait for ACK
            resp = self._read_response(self.CMD_TIMEOUT)
            if resp is None or resp.cmd != CMD.ACK:
                return None

            # Receive image chunks
            total_expected = width * height * 10 // 8
            image_data = bytearray(total_expected)
            received = 0
            deadline = time.monotonic() + timeout
            buf = bytearray()

            while time.monotonic() < deadline:
                chunk = self._port.read(1024)
                if chunk:
                    buf.extend(chunk)

                while len(buf) >= 2:
                    if buf[:2] == IMG_EOT_HEADER:
                        if len(buf) >= 6:
                            return bytes(image_data[:received])
                        break

                    if buf[:2] == IMG_DATA_HEADER:
                        if len(buf) < 7:
                            break
                        seq = (buf[2] << 8) | buf[3]
                        chunk_len = (buf[4] << 8) | buf[5]
                        total_pkt = 7 + chunk_len
                        if len(buf) < total_pkt:
                            break
                        data = buf[6:6+chunk_len]
                        cs = buf[6+chunk_len]

                        # Verify chunk checksum
                        calc = buf[2] ^ buf[3] ^ buf[4] ^ buf[5]
                        for b in data:
                            calc ^= b
                        calc &= 0xFF

                        offset = seq * 512
                        if calc == cs and offset < total_expected:
                            end = min(offset + chunk_len, total_expected)
                            image_data[offset:end] = data[:end-offset]
                            received = max(received, end)

                        if progress_cb:
                            progress_cb(received, total_expected)

                        buf = buf[total_pkt:]
                    else:
                        buf.pop(0)

            return None  # timeout
