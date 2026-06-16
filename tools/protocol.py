"""UART protocol: frame builder, parser, checksum (spec §6)."""
from dataclasses import dataclass
from enum import IntEnum


class CMD(IntEnum):
    WRITE_REG    = 0x01
    READ_REG     = 0x02
    READ_STATUS  = 0x03
    CAPTURE      = 0x04
    GPIO_CTRL    = 0x05
    RESET_SEQ    = 0x06
    SET_SOURCE   = 0x07
    SET_PORT     = 0x08
    CLR_ERR      = 0x0A
    ACK          = 0x80
    ERR          = 0x81


class ERR(IntEnum):
    I2C_NACK       = 0x01
    I2C_TIMEOUT    = 0x02
    INVALID_CMD    = 0x03
    INVALID_PARAM  = 0x04
    VDMA_FAIL      = 0x05
    MIPI_NOT_READY = 0x06
    CHECKSUM_ERR   = 0x07
    BUSY           = 0x08


HEADER = b'\xAA\x55'

# Image stream headers
IMG_DATA_HEADER = b'\xBB\x66'
IMG_EOT_HEADER  = b'\xBB\x99'


class FrameError(Exception):
    pass


@dataclass
class ParsedFrame:
    cmd: int
    payload: bytes


def calc_checksum(cmd: int, payload: bytes) -> int:
    length = len(payload)
    cs = cmd ^ (length >> 8) ^ (length & 0xFF)
    for b in payload:
        cs ^= b
    return cs & 0xFF


def build_frame(cmd: int, payload: bytes = b'') -> bytes:
    length = len(payload)
    cs = calc_checksum(cmd, payload)
    return (HEADER
            + bytes([cmd, length >> 8, length & 0xFF])
            + payload
            + bytes([cs]))


def parse_frame(data: bytes) -> ParsedFrame:
    if len(data) < 6:
        raise FrameError(f"Frame too short: {len(data)} bytes")
    if data[:2] != HEADER:
        raise FrameError(f"Bad header: {data[:2].hex()}")
    cmd = data[2]
    length = (data[3] << 8) | data[4]
    if len(data) < 5 + length + 1:
        raise FrameError(f"Frame truncated: need {5+length+1}, got {len(data)}")
    payload = data[5:5+length]
    checksum = data[5+length]
    expected = calc_checksum(cmd, payload)
    if checksum != expected:
        raise FrameError(f"Checksum mismatch: got 0x{checksum:02X}, expected 0x{expected:02X}")
    return ParsedFrame(cmd=cmd, payload=payload)


def parse_status(payload: bytes) -> dict:
    """Parse 0x03 response 8-byte payload into dict."""
    if len(payload) != 8:
        raise FrameError(f"Status payload must be 8 bytes, got {len(payload)}")
    return {
        'port': payload[0],
        'rate_mbps': (payload[1] << 8) | payload[2],
        'ecc_err': (payload[3] << 8) | payload[4],
        'crc_err': (payload[5] << 8) | payload[6],
        'link_up': bool(payload[7]),
    }
