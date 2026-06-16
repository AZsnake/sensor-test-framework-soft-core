import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from init_script import parse_xlsx_registers

def test_parse_returns_list_of_tuples(tmp_path):
    """Verify parser returns (addr, data) tuples from a mock xlsx."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Address", "Data"])
    ws.append(["0x0100", "0xFF"])
    ws.append(["0x0101", "0x00"])
    ws.append(["0x3020", "0xAB"])
    fpath = tmp_path / "test_regs.xlsx"
    wb.save(fpath)

    regs = parse_xlsx_registers(str(fpath))
    assert len(regs) == 3
    assert regs[0] == (0x0100, 0xFF)
    assert regs[2] == (0x3020, 0xAB)
