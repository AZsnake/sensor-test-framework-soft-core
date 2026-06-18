"""MIPI RAW10 unpack (4 pixels per 5 bytes)."""
import numpy as np


def decode_raw10(data: bytes, width: int, height: int) -> np.ndarray:
    """Unpack MIPI RAW10 to a 16-bit Bayer array."""
    stride = width * 10 // 8
    expected = stride * height
    if len(data) < expected:
        padded = data + b'\x00' * (expected - len(data))
    else:
        padded = data[:expected]

    raw = np.frombuffer(padded, dtype=np.uint8).reshape(height, stride)
    img = np.zeros((height, width), dtype=np.uint16)

    for col_group in range(width // 4):
        base = col_group * 5
        b0, b1, b2, b3, b4 = (raw[:, base], raw[:, base + 1],
                              raw[:, base + 2], raw[:, base + 3], raw[:, base + 4])
        img[:, col_group * 4] = (b0.astype(np.uint16) << 2) | ((b4 >> 0) & 0x03)
        img[:, col_group * 4 + 1] = (b1.astype(np.uint16) << 2) | ((b4 >> 2) & 0x03)
        img[:, col_group * 4 + 2] = (b2.astype(np.uint16) << 2) | ((b4 >> 4) & 0x03)
        img[:, col_group * 4 + 3] = (b3.astype(np.uint16) << 2) | ((b4 >> 6) & 0x03)

    return img
