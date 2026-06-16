import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from protocol import build_frame, parse_frame, calc_checksum, CMD, FrameError

class TestChecksum:
    def test_empty_payload(self):
        cs = calc_checksum(0x06, b'')
        assert cs == 0x06  # CMD ^ 0x00 ^ 0x00

    def test_with_payload(self):
        cs = calc_checksum(0x01, bytes([0x00, 0x16, 0xFF]))
        expected = 0x01 ^ 0x00 ^ 0x03 ^ 0x00 ^ 0x16 ^ 0xFF
        assert cs == expected

class TestBuildFrame:
    def test_reset_cmd(self):
        frame = build_frame(CMD.RESET_SEQ)
        assert frame[:2] == b'\xAA\x55'
        assert frame[2] == CMD.RESET_SEQ
        assert frame[3:5] == b'\x00\x00'
        assert len(frame) == 6

    def test_write_reg(self):
        frame = build_frame(CMD.WRITE_REG, bytes([0x00, 0x16, 0xFF]))
        assert frame[2] == CMD.WRITE_REG
        assert frame[3:5] == b'\x00\x03'
        assert frame[5:8] == bytes([0x00, 0x16, 0xFF])

class TestParseFrame:
    def test_ack(self):
        frame = build_frame(CMD.ACK, bytes([CMD.RESET_SEQ]))
        result = parse_frame(frame)
        assert result.cmd == CMD.ACK
        assert result.payload == bytes([CMD.RESET_SEQ])

    def test_status_response(self):
        payload = bytes([1, 0x05, 0x78, 0, 0, 0, 0, 1])  # port=1,rate=1400,ecc=0,crc=0,linkup=1
        frame = build_frame(CMD.READ_STATUS, payload)
        result = parse_frame(frame)
        assert result.cmd == CMD.READ_STATUS
        assert result.payload[0] == 1
        assert (result.payload[1] << 8 | result.payload[2]) == 1400
        assert result.payload[7] == 1

    def test_bad_checksum(self):
        frame = build_frame(CMD.RESET_SEQ)
        frame = frame[:-1] + bytes([frame[-1] ^ 0xFF])
        with pytest.raises(FrameError):
            parse_frame(frame)

    def test_bad_header(self):
        with pytest.raises(FrameError):
            parse_frame(b'\xBB\x55\x06\x00\x00\x06')
