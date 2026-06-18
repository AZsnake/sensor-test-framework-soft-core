#!/usr/bin/env python3
"""从一张 RAW10 抓图里反推 sensor 实际行宽(stride), 用于诊断"对角剪切"。

对角剪切 = 解码用的行宽 ≠ sensor 实际行宽。本工具扫描候选行宽, 取"相邻行差异
最小"的那个 = 真实行宽(此时图像不再逐行错位)。

用法:
  python tools/scripts/find_stride.py <capture.raw>
  python tools/scripts/find_stride.py capture.raw --min-w 1900 --max-w 4800
"""
from __future__ import annotations

import argparse

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", help="保存的 .raw 文件")
    ap.add_argument("--min-w", type=int, default=1900, help="候选宽度下界(px)")
    ap.add_argument("--max-w", type=int, default=4800, help="候选宽度上界(px)")
    args = ap.parse_args()

    data = np.fromfile(args.raw, dtype=np.uint8).astype(np.int16)
    n = len(data)
    print(f"文件: {args.raw}  字节数: {n}")

    lo, hi = 500, min(6000, n // 8)
    results = []
    for sb in range(lo, hi + 1):
        rows = n // sb
        if rows < 8:
            continue
        a = data[:rows * sb].reshape(rows, sb)
        diff = np.mean(np.abs(a[1:] - a[:-1]))
        results.append((diff, sb, rows))

    results.sort()
    print(f"\n扫描字节 stride {lo}..{hi}; 相邻行差异最小的候选:")
    print(f"{'stride_B':>9} {'rows':>6} {'若RAW10宽':>10} {'行间差异':>10}")
    for diff, sb, rows in results[:10]:
        w = sb * 8 // 10
        print(f"{sb:>9} {rows:>6} {w:>10} {diff:>10.2f}")

    best_sb = results[0][1]
    base = results[-1][0]
    print(f"\n→ 真实行字节 stride ≈ {best_sb} B  (≈ {best_sb*8//10} px @RAW10)")
    print(f"   最小差异 {results[0][0]:.2f} vs 背景 {base:.2f}  "
          f"({'明显命中' if results[0][0] < base*0.5 else '不明显, 见下'})")
    for name, w in (("2016(旧)", 2016), ("2328(C4目标)", 2328), ("4656(全宽)", 4656)):
        sb = w * 10 // 8
        rows = n // sb
        if rows > 8:
            a = data[:rows * sb].reshape(rows, sb)
            d = float(np.mean(np.abs(a[1:] - a[:-1])))
        else:
            d = float('nan')
        print(f"   参考 {name:14s} stride={sb}B 行间差异={d:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
