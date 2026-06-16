# MIPI_VU13P

VU13P (xcvu13p-fhga2104) 平台 IMX298 相机验证:MicroBlaze 固件 bit-bang I2C 配置相机,官方 MIPI CSI-2 RX Subsystem 接收 2-Lane RAW10,URAM 单帧缓存经 UART 回传 PC。由 Versal VP1902 工程(`../MIPI`)迁移而来,协议/固件/上位机大量复用。

设计规格:[docs/specs/2026-06-12-vu13p-camera-validation-design.md](docs/specs/2026-06-12-vu13p-camera-validation-design.md)

**当前阶段:** 平台实现中。`fpga/scripts/create_project.tcl` 一键重建工程+BD;`fpga/scripts/run_synth_drc.tcl` 综合+DRC(spec §4.4 P0-4 空跑)。上板前仍须闭环 P0 先决项(Bank 62 1.2V 供电 / VRP / CLK 对改线,需查主板原理图)。

```
fpga/constraints/vu13p_pins.xdc   # 板级引脚约束(MIPI 引脚由 IP 管理)
fpga/rtl/axis_uram_framebuf.v     # URAM 帧缓冲(复用)
fpga/scripts/create_project.tcl   # 工程+BD 构建
fpga/vitis/mipi_fw/src/           # MicroBlaze V 裸机固件(复用+适配)
tools/                            # PC 上位机(协议不变,原样复用)
```
