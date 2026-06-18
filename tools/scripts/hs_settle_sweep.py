#!/usr/bin/env python3
"""在线扫描 D-PHY HS_SETTLE, 找出能解出 MIPI 包的采样窗口值。

适用场景: 时钟 lane 已进 HS(LinkUp=True)、数据 lane 有 LP 活动、但 pkt_count=0、
零 SoT/ECC/CRC 错 —— 典型 HS 采样窗口(HS_SETTLE)对不齐, 而非接线/配置问题。

前提:
  1. 固件已含 CMD_SET_HS_SETTLE (0x0C);
  2. bit流 build 时 DPY_EN_REG_IF=true (否则 D-PHY 寄存器块不存在, 回读恒 0);
  3. sensor 正在出流 (脚本会先检查 LinkUp / 时钟 lane HS)。

用法:
  python tools/scripts/hs_settle_sweep.py COM14
  python tools/scripts/hs_settle_sweep.py COM14 --min-ns 60 --max-ns 170 --dwell 0.4
"""
from __future__ import annotations

import argparse

import _bootstrap  # noqa: F401, E402
from serial_mgr import SerialManager  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="在线扫描 D-PHY HS_SETTLE")
    ap.add_argument("port", help="串口, 如 COM14")
    ap.add_argument("--min-ns", type=float, default=70.0, help="扫描下界(ns), 默认 70")
    ap.add_argument("--max-ns", type=float, default=160.0, help="扫描上界(ns), 默认 160")
    ap.add_argument("--dwell", type=float, default=0.35,
                    help="每个值的停留/采样窗口(秒), 默认 0.35")
    args = ap.parse_args()

    sm = SerialManager()
    sm.connect(args.port)
    try:
        results = sm.sweep_hs_settle(min_ns=args.min_ns, max_ns=args.max_ns,
                                     dwell=args.dwell, log=print)
        return 0 if results else 1
    finally:
        sm.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
