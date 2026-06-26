# MIPI 测试框架

面向 **Xilinx VU13P + IMX298** 的 MIPI CSI-2 相机采集与验证框架：传感器 I2C 配置、2-Lane RAW10 接收、URAM 帧缓冲、MicroBlaze 固件与 PySide6 上位机联调。

**Vivado Block Design：** `mipi_platform` · **固件应用：** `mipi_fw`

> 本仓库为开源 FPGA 验证参考实现。不含板级原理图或未公开的硬件资料。引脚约束需结合具体板卡自行准备（参考 `fpga/constraints/vu13p_pins.template.xdc`），clone 后不能直接综合上板。

许可证：[MIT](LICENSE)（第三方模块见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）

## 姊妹项目

同一 **VU13P + IMX298** MIPI CSI-2 验证平台的两套实现，共享 Vivado Block Design（`mipi_platform`）与 PySide6 上位机（`tools/` UART 协议兼容）：

| 仓库 | 说明 |
|------|------|
| [**sensor-test-framework-soft-core**](https://github.com/AZsnake/sensor-test-framework-soft-core) | **本仓库** — MicroBlaze 固件 + Vitis；D-PHY / Lane 深度联调、HS_SETTLE 扫描 |
| [**sensor-test-framework-pure-rtl**](https://github.com/AZsnake/sensor-test-framework-pure-rtl) | 姊妹项目 — 纯 RTL `mipi_sys_ctrl`，无 MicroBlaze / Vitis；init mem BRAM 上电初始化 |

---

## 功能亮点

| 方向 | 内容 |
|------|------|
| 端到端采集 | I2C 传感器初始化 → CSI-2 RAW10 接收 → URAM 缓存 → UART 回传 → PC 解码显示 |
| CSI-2 / D-PHY | 2 数据 Lane + 1 时钟 Lane；ECC/CRC 统计；HS_SETTLE 在线扫描 |
| 固件 | MicroBlaze 裸机：协议解析、GPIO bit-bang I2C、单帧抓取、链路诊断 |
| 联调诊断 | 链路状态、Lane/D-PHY 寄存器 dump、行 stride 反推脚本 |
| 主机工具 | PySide6 GUI + CLI（HS_SETTLE 扫描、寄存器批量下发） |
| 工程化 | `create_project.tcl` 一键重建 BD；Vivado → XSA → Vitis 标准流程 |

当前基线输出：**2016×1512 @ ~21 fps**（2-Lane RAW10）。

---

## 仓库结构

```
sensor-test-framework-soft-core/
├── fpga/
│   ├── constraints/          # vu13p_pins.template.xdc（需复制为 vu13p_pins.xdc）
│   ├── scripts/              # create_project.tcl
│   ├── vitis/                # mipi_fw 固件工程
│   └── vivado/               # 生成工程目录（.gitignore，本地构建产物）
├── tools/                    # PySide6 上位机 + UART 协议库 + CLI
├── docs/
└── README.md
```

---

## 架构总览

![mipi_platform Block Design](docs/mipi_platform_v0.0.5.png)

```
传感器 (I2C)     MIPI CSI-2 RX      URAM 帧缓冲       UART          上位机
───────────  →  D-PHY + 协议解析  →  AXIS 写缓存  →  分块传输  →  RAW10 解码 / GUI
```

```
mipi_platform (BD)
├── MicroBlaze + AXI UART / GPIO
├── MIPI CSI-2 RX Subsystem → axis_uram_framebuf
└── System ILA（联调）
```

---

## 上位机工具

![MIPI VU13P 上位机](docs/python_gui.png)

PySide6 图形界面提供串口连接、链路状态、多档抓图分辨率、RAW10 解码预览，以及 PNG / RAW 保存。详见 [`tools/README.md`](tools/README.md)。

---

## 快速上手

**环境：** Vivado **2024.2** · Vitis **2024.2** · Python 3.10+

1. 复制引脚模板，按实际原理图填写 `PIN_*` 变量：

   ```bash
   cp fpga/constraints/vu13p_pins.template.xdc fpga/constraints/vu13p_pins.xdc
   ```

   Windows CMD：`copy fpga\constraints\vu13p_pins.template.xdc fpga\constraints\vu13p_pins.xdc`

2. 生成 Vivado 工程（需已安装 Vivado）：

   ```bash
   vivado -mode batch -source fpga/scripts/create_project.tcl
   ```

3. Vivado 中综合、实现、生成比特流并导出 XSA；Vitis 导入 XSA，编译 `mipi_fw` 并下载至板卡。

4. 安装主机工具并启动 GUI：

   ```bash
   cd tools
   pip install -r requirements.txt
   ./run_gui.sh          # Linux / macOS
   run_gui.bat           # Windows
   ```

5. 连接串口 → **读状态** 确认链路已建立 → **抓图** 验证出图。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [`tools/README.md`](tools/README.md) | Python 上位机与 CLI 脚本说明 |
| [`fpga/scripts/create_project.tcl`](fpga/scripts/create_project.tcl) | Vivado 工程 / BD 一键生成 |
| [`tools/lib/protocol.py`](tools/lib/protocol.py) | UART 协议（与固件一致） |

传感器数据手册请从厂商官网获取：

| 器件 | 官网 |
|------|------|
| IMX298 | [sony-semicon.com](https://www.sony-semicon.com/en/products/is/industry/imx298.html) |

---

## 联调能力

| 命令 | 用途 |
|------|------|
| 链路状态 `0x03` | D-PHY 线速率、ECC/CRC 累计、时钟 Lane HS 状态 |
| Lane 诊断 `0x0B` | CSI-2 RX 子系统 CCR/CSR/ISR 与各 Lane 信息寄存器 |
| D-PHY 诊断 `0x0D` | per-lane Mode / InitDone / CalibComplete / HSAbort / 包计数 |
| HS_SETTLE 扫描 `0x0C` | 在线扫描采样窗口 |
| `find_stride.py` | 从抓图文件反推实际行 stride |

---

## 备注

- 目标器件：`xcvu13p-fhga2104-2-i`（请按实际板卡调整）。
- 不含板级原理图、真实管脚约束或未公开的硬件资料。
- 芯片厂商寄存器表、数据手册等受版权约束的文件**未包含或未跟踪**；固件中的初始化表仅为参考配置，不代表厂商推荐设置。
- Xilinx IP 与第三方模块遵循各自许可条款（见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)）。
