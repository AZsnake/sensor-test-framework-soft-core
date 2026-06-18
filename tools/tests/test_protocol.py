import pytest

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
    def test_roundtrip(self):
        frame = build_frame(CMD.READ_STATUS)
        parsed = parse_frame(frame)
        assert parsed.cmd == CMD.READ_STATUS
        assert parsed.payload == b''

    def test_bad_checksum(self):
        frame = bytearray(build_frame(CMD.RESET_SEQ))
        frame[-1] ^= 0xFF
        with pytest.raises(FrameError, match="Checksum"):
            parse_frame(bytes(frame))

    def test_bad_header(self):
        with pytest.raises(FrameError, match="Bad header"):
            parse_frame(b'\x00\x00\x06\x00\x00\x06')
