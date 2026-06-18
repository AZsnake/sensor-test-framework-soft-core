#!/usr/bin/env python3
"""从 xlsx 批量下发 IMX298 初始化寄存器 (UART 0x01 WRITE_REG)。"""
from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401, E402
from init_script import download_init_script, parse_xlsx_registers  # noqa: E402
from serial_mgr import SerialManager  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="下载 IMX298 寄存器表 (xlsx → UART)")
    ap.add_argument("port", help="串口, 如 COM14")
    ap.add_argument("xlsx", help="寄存器表 xlsx (含 Address / Data 列)")
    args = ap.parse_args()

    try:
        registers = parse_xlsx_registers(args.xlsx)
    except (ValueError, OSError) as e:
        print(f"解析失败: {e}", file=sys.stderr)
        return 1

    print(f"共 {len(registers)} 条寄存器, 开始下发...")
    sm = SerialManager()
    sm.connect(args.port)
    try:
        ok, err = download_init_script(sm, registers, progress_cb=lambda i, t: print(
            f"\r进度 {i}/{t}", end="", flush=True))
        print()
        if not ok:
            print(f"失败: {err}", file=sys.stderr)
            return 1
        print("完成")
        return 0
    finally:
        sm.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
