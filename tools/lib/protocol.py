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
    LANE_DIAG    = 0x0B
    SET_HS_SETTLE = 0x0C
    DPHY_DIAG    = 0x0D
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


# CSI-2 RX 子系统 lane 诊断寄存器顺序 (与固件 cmd_lane_diag 一致)
LANE_DIAG_REGS = ('CCR', 'CSR', 'ISR', 'CLK_LANE', 'LANE0', 'LANE1')


def parse_lane_diag(payload: bytes) -> dict:
    """Parse 0x0B response: 6 × u32 大端 -> {寄存器名: 值} + 判读标志。"""
    if len(payload) != 24:
        raise FrameError(f"Lane diag payload must be 24 bytes, got {len(payload)}")
    regs = {name: int.from_bytes(payload[i*4:i*4+4], 'big')
            for i, name in enumerate(LANE_DIAG_REGS)}
    clk, l0, l1 = regs['CLK_LANE'], regs['LANE0'], regs['LANE1']
    regs['flags'] = {
        'clk_stop':   bool(clk & 0x2),          # 时钟 lane 仍在 Stop(未进 HS)
        'l0_sot_err': bool(l0 & 0x1),
        'l0_sotsync_err': bool(l0 & 0x2),
        'l0_stop':    bool(l0 & 0x20),
        'l1_sot_err': bool(l1 & 0x1),
        'l1_sotsync_err': bool(l1 & 0x2),
        'l1_stop':    bool(l1 & 0x20),
        'pkt_count':  (regs['CSR'] >> 16) & 0xFFFF,
    }
    return regs


# D-PHY 状态寄存器顺序 (与固件 cmd_dphy_diag 一致)
DPHY_DIAG_REGS = ('CTRL', 'CLSTATUS', 'DL0STATUS', 'DL1STATUS',
                  'HSSETTLE_L0', 'HSSETTLE_L1')


def _parse_dphy_data_lane(v: int) -> dict:
    """DLxSTATUS 位域 (xdphy_hw.h)。"""
    return {
        'mode': v & 0x3,
        'ulps': bool(v & (1 << 2)),
        'init_done': bool(v & (1 << 3)),
        'hs_abort': bool(v & (1 << 4)),
        'esc_abort': bool(v & (1 << 5)),
        'stop': bool(v & (1 << 6)),
        'calib_complete': bool(v & (1 << 7)),
        'calib_status': bool(v & (1 << 8)),
        'pkt_count': (v >> 16) & 0xFFFF,
    }


def parse_dphy_diag(payload: bytes) -> dict:
    """Parse 0x0D 响应: 6×u32 大端 -> 寄存器值 + per-lane 判读。"""
    if len(payload) != 24:
        raise FrameError(f"DPHY diag payload must be 24 bytes, got {len(payload)}")
    regs = {name: int.from_bytes(payload[i*4:i*4+4], 'big')
            for i, name in enumerate(DPHY_DIAG_REGS)}
    cl = regs['CLSTATUS']
    regs['flags'] = {
        'dphy_en': bool(regs['CTRL'] & 0x2),
        'clk': {
            'mode': cl & 0x3,
            'ulps': bool(cl & (1 << 2)),
            'init_done': bool(cl & (1 << 3)),
            'stop': bool(cl & (1 << 4)),
            'err_ctrl': bool(cl & (1 << 5)),
        },
        'dl0': _parse_dphy_data_lane(regs['DL0STATUS']),
        'dl1': _parse_dphy_data_lane(regs['DL1STATUS']),
    }
    return regs


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
