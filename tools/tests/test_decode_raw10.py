import numpy as np
import pytest

from raw10 import decode_raw10


class TestDecodeRaw10:
    def test_four_pixel_row(self):
        # P0=4, P1=8, P2=12, P3=16 packed as MIPI RAW10
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x00])
        img = decode_raw10(data, width=4, height=1)
        assert img.shape == (1, 4)
        assert img.dtype == np.uint16
        np.testing.assert_array_equal(img[0], [4, 8, 12, 16])

    def test_low_bits_in_fifth_byte(self):
        # P0=1023 (0x3FF): b0=0xFF, low2=0x03
        data = bytes([0xFF, 0x00, 0x00, 0x00, 0x03])
        img = decode_raw10(data, width=4, height=1)
        assert img[0, 0] == 1023

    def test_pads_short_buffer(self):
        data = bytes([0x01, 0x02, 0x03, 0x04, 0x00])
        img = decode_raw10(data, width=4, height=2)
        assert img.shape == (2, 4)
        np.testing.assert_array_equal(img[0], [4, 8, 12, 16])
        np.testing.assert_array_equal(img[1], [0, 0, 0, 0])

    def test_640x480_size(self):
        w, h = 640, 480
        expected_bytes = w * h * 10 // 8
        data = bytes(expected_bytes)
        img = decode_raw10(data, w, h)
        assert img.shape == (h, w)
