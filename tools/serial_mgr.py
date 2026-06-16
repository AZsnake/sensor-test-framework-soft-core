"""Serial port manager for CH9114 UART_AP communication."""
import time
import threading
from typing import Optional, Callable

import serial
import serial.tools.list_ports

from protocol import (build_frame, parse_frame, ParsedFrame, FrameError,
                      CMD, ERR, HEADER, IMG_DATA_HEADER, IMG_EOT_HEADER,
                      parse_status)


class SerialManager:
    BAUD = 230400
    CMD_TIMEOUT = 0.5
    CAPTURE_TIMEOUT_640 = 10.0
    CAPTURE_TIMEOUT_320 = 3.0

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
        timeout = self.CAPTURE_TIMEOUT_640 if width >= 640 else self.CAPTURE_TIMEOUT_320
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
                            total_bytes = int.from_bytes(buf[2:6], 'big')
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
