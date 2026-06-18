"""Parse IMX298 register init script from xlsx and batch-download via UART."""
import time
from typing import Optional, Callable

import openpyxl

from protocol import CMD, ERR
from serial_mgr import SerialManager


def parse_xlsx_registers(filepath: str) -> list[tuple[int, int]]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(min_row=1, values_only=True))
    wb.close()

    if not rows:
        return []

    header = [str(c).strip().lower() if c else '' for c in rows[0]]
    addr_col = None
    data_col = None
    for i, h in enumerate(header):
        if 'addr' in h:
            addr_col = i
        elif 'data' in h or 'value' in h:
            data_col = i

    if addr_col is None or data_col is None:
        print(f"Column mapping: {list(enumerate(header))}")
        raise ValueError("Cannot find Address/Data columns in xlsx. "
                         "Expected column headers containing 'addr' and 'data'/'value'.")

    print(f"Init Script: addr_col={addr_col} ({header[addr_col]}), "
          f"data_col={data_col} ({header[data_col]})")

    registers = []
    for row in rows[1:]:
        if row[addr_col] is None or row[data_col] is None:
            continue
        addr_val = row[addr_col]
        data_val = row[data_col]

        if isinstance(addr_val, str):
            addr = int(addr_val, 16) if addr_val.startswith('0x') else int(addr_val)
        else:
            addr = int(addr_val)

        if isinstance(data_val, str):
            data = int(data_val, 16) if data_val.startswith('0x') else int(data_val)
        else:
            data = int(data_val)

        registers.append((addr & 0xFFFF, data & 0xFF))

    return registers


def download_init_script(
    mgr: SerialManager,
    registers: list[tuple[int, int]],
    progress_cb: Optional[Callable[[int, int], None]] = None,
    batch_size: int = 64,
) -> tuple[bool, Optional[str]]:
    total = len(registers)
    for i, (addr, data) in enumerate(registers):
        try:
            resp = mgr.write_reg(addr, data)
            if resp.cmd == CMD.ERR:
                err_name = ERR(resp.payload[0]).name if resp.payload else 'UNKNOWN'
                return False, f"Error at reg 0x{addr:04X}: {err_name}"
        except TimeoutError:
            return False, f"Timeout at reg 0x{addr:04X} ({i+1}/{total})"

        if progress_cb:
            progress_cb(i + 1, total)

        time.sleep(0.001)

    return True, None
