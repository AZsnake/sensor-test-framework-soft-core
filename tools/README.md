# tools/

MIPI 工程配套 PC 端脚本。**不加入 Vivado / Vitis 工程。** 各功能按子目录分类。

## 目录结构

```
tools/
├── run_gui.bat / run_gui.sh       # 启动 GUI
├── run_tests.bat / run_tests.sh   # 运行单元测试
├── requirements.txt
├── pytest.ini                     # pytest 配置 (pythonpath=lib)
├── lib/                           # 协议 / 串口 / RAW10 解码
├── gui/                           # PySide6 验证平台
├── scripts/                       # 命令行工具
│   ├── find_stride.py
│   ├── hs_settle_sweep.py
│   └── download_regs.py
└── tests/
```

## 安装

```bash
cd tools
pip install -r requirements.txt
```

Linux 首次使用 shell 脚本需赋予执行权限：

```bash
chmod +x run_gui.sh run_tests.sh
```

## 使用

### Windows

| 任务 | 命令 |
|------|------|
| GUI | `run_gui.bat` |
| 单元测试 | `run_tests.bat` |
| 行宽诊断 | `python scripts\find_stride.py capture.raw` |
| HS_SETTLE 扫描 | `python scripts\hs_settle_sweep.py COM14` |
| 寄存器下发 | `python scripts\download_regs.py COM14 regs.xlsx` |

### Linux / macOS

| 任务 | 命令 |
|------|------|
| GUI | `./run_gui.sh` |
| 单元测试 | `./run_tests.sh` |
| 行宽诊断 | `python3 scripts/find_stride.py capture.raw` |
| HS_SETTLE 扫描 | `python3 scripts/hs_settle_sweep.py /dev/ttyUSB0` |
| 寄存器下发 | `python3 scripts/download_regs.py /dev/ttyUSB0 regs.xlsx` |

也可直接：`python gui/main.py`、`python -m pytest`（在 `tools/` 目录下）。

## 说明

- `lib/` 为共享层：GUI 与 `scripts/` 均通过 `lib` 访问固件 UART 协议。
- 抓图宽度须与 sensor 实际行宽一致（当前基线 **2016**）；见 `gui/control_panel.py` 预设。
- `scripts/_bootstrap.py` 负责把 `tools/` 与 `tools/lib` 加入 `sys.path`，CLI 脚本无需手动改 CWD。
- Linux 串口一般为 `/dev/ttyUSB0`、`/dev/ttyACM0` 等；当前用户需 dialout 组权限（`sudo usermod -aG dialout $USER`）。
