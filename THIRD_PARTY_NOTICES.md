# 第三方声明

## 传感器初始化表 — Sony IMX298

`fpga/vitis/mipi_fw/src/imx298_init_regs.h` 中的寄存器序列来自个人联调配置，**不代表 Sony 官方推荐设置**。IMX298 数据手册与标准寄存器表受 Sony 版权约束，**本仓库不跟踪** `docs/specs/` 下的厂商 PDF / Excel。

如需再分发本仓库，请自行确认是否有权包含上述寄存器内容，或改用公开参考实现替换。

## Xilinx IP 与工具链

Block Design 中使用的 MIPI CSI-2 RX Subsystem、MicroBlaze、AXI 外设、System ILA 等 Xilinx IP，以及 Vivado / Vitis 生成的工程产物，遵循 [AMD Xilinx 许可条款](https://www.xilinx.com/support/terms/index.html)。`docs/bd_design/` 下的 Block Design 导出图仅供学习参考。

## 芯片数据手册（`docs/specs/`）

`docs/specs/` 目录下的 PDF 文件版权归各芯片厂商所有。**本仓库不再跟踪这些文件**，请直接从厂商官网下载最新版本：

| 器件 | 下载地址 |
|------|---------|
| IMX298 | [sony-semicon.com](https://www.sony-semicon.com/en/products/is/industry/imx298.html) |

## MIPI 规范

MIPI Alliance 规范文档受联盟版权约束，请通过 [mipi.org](https://www.mipi.org/) 获取授权副本。
