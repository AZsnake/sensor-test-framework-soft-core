# ============================================================
# VU13P 板级管脚约束 — 模板 (可提交 Git)
#
# 使用:
#   1. 复制为本目录下的 vu13p_pins.xdc (该文件已 .gitignore, 勿提交)
#      cp vu13p_pins.xdc.template vu13p_pins.xdc
#   2. 根据**本机板卡原理图**填写下方 PIN_* 变量
#   3. create_project.tcl / Vivado 综合前确认无空 PIN_*
#
# 器件: xcvu13p-fhga2104-2-i
# create_clock 由 BD/clk_wiz 自动生成, 勿在此手写 (UG949 / AR 18-1055)
# ============================================================

# ---------------------------------------------------------------------------
# 填写区 — PACKAGE_PIN 仅来自你的硬件文档, 勿从公开仓库抄录他人板卡管脚
# ---------------------------------------------------------------------------
set PIN_CLK_19M2   ""   ;# 系统时钟, 19.2 MHz, 须为 GC/CMT 可用脚, 典型 Bank 63 LVCMOS18
set PIN_UART_TX    ""   ;# UART 发送
set PIN_UART_RX    ""   ;# UART 接收

set PIN_CAM_RESET  ""   ;# cam_gpio_tri_io[0] 传感器 RESET / XCLR
set PIN_CAM_PWDN   ""   ;# cam_gpio_tri_io[1] 传感器 PWDN
set PIN_CAM_SCL    ""   ;# cam_gpio_tri_io[2] I2C SCL (开漏, 建议 PULLUP)
set PIN_CAM_SDA    ""   ;# cam_gpio_tri_io[3] I2C SDA (开漏, 建议 PULLUP)
set PIN_CAM_VSYNC  ""   ;# cam_vsync[0] 帧同步输入 (可选)

set PIN_LED_0      ""
set PIN_LED_1      ""
set PIN_LED_2      ""
set PIN_LED_3      ""
set PIN_LED_4      ""
set PIN_LED_5      ""
set PIN_LED_6      ""
set PIN_LED_7      ""

# ---------------------------------------------------------------------------
# 系统时钟
# ---------------------------------------------------------------------------
set_property -dict [list PACKAGE_PIN $PIN_CLK_19M2 IOSTANDARD LVCMOS18] [get_ports pad_clk_19m2]

# ---------------------------------------------------------------------------
# UART (与固件 UART_BAUD 230400 对应)
# ---------------------------------------------------------------------------
set_property -dict [list PACKAGE_PIN $PIN_UART_TX IOSTANDARD LVCMOS18] [get_ports o_uart_tx]
set_property -dict [list PACKAGE_PIN $PIN_UART_RX IOSTANDARD LVCMOS18] [get_ports i_uart_rx]

# ---------------------------------------------------------------------------
# 相机控制 GPIO (AXI GPIO CH1 三态, 4-bit)
#   bit0 = RESET   bit1 = PWDN   bit2 = SCL   bit3 = SDA
# I2C bit-bang: 释放(TRI=1) 后靠上拉拉高; 板级建议 2.2k~4.7k 外部上拉至 I2C 域电压
# ---------------------------------------------------------------------------
set_property -dict [list PACKAGE_PIN $PIN_CAM_RESET IOSTANDARD LVCMOS18] [get_ports {cam_gpio_tri_io[0]}]
set_property -dict [list PACKAGE_PIN $PIN_CAM_PWDN  IOSTANDARD LVCMOS18] [get_ports {cam_gpio_tri_io[1]}]
set_property -dict [list PACKAGE_PIN $PIN_CAM_SCL    IOSTANDARD LVCMOS18 PULLUP true] [get_ports {cam_gpio_tri_io[2]}]
set_property -dict [list PACKAGE_PIN $PIN_CAM_SDA    IOSTANDARD LVCMOS18 PULLUP true] [get_ports {cam_gpio_tri_io[3]}]

set_property -dict [list PACKAGE_PIN $PIN_CAM_VSYNC IOSTANDARD LVCMOS18] [get_ports {cam_vsync[0]}]

# ---------------------------------------------------------------------------
# LED (AXI GPIO CH2, pad_output_d[7:0])
# ---------------------------------------------------------------------------
set_property -dict [list PACKAGE_PIN $PIN_LED_0 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[0]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_1 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[1]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_2 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[2]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_3 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[3]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_4 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[4]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_5 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[5]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_6 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[6]}]
set_property -dict [list PACKAGE_PIN $PIN_LED_7 IOSTANDARD LVCMOS18] [get_ports {pad_output_d[7]}]

# ---------------------------------------------------------------------------
# MIPI CSI-2 RX (典型为 Bank 62, MIPI_DPHY_DCI, VCCO = 1.2 V)
#
# 差分 Lane 的 PACKAGE_PIN 由 MIPI CSI-2 RX Subsystem IP 的 Pin Assignment 生成,
# 不要在此重复 LOC, 以免与 IP 自带 XDC 冲突。
#
# 步骤概要:
#   1. BD 中打开 mipi_csi2_rx → Pin Assignment
#   2. 先选 Clock Lane, 再选 Data Lane (PG232 要求顺序)
#   3. 确认 Lane 与 byte group / Bank VCCO 1.2 V 一致
#   4. 若换脚后 IP 导出 bg*_pin0_nc 辅助端口, 运行 scripts/fix_mipi_nc_export.tcl
#
# 辅助 NC 端口仅需补 IOSTANDARD (IP 已约束 LOC):
#   默认 LVCMOS18 会与 MIPI_DPHY_DCI 的 1.2 V Bank 冲突 (Place 30-372)
# ---------------------------------------------------------------------------
set_property IOSTANDARD LVCMOS12 [get_ports bg0_pin0_nc_0]
set_property IOSTANDARD LVCMOS12 [get_ports bg2_pin0_nc_0]

# 若目标 Bank 未接 VRP 而相邻 Bank 已接 240 Ω, 可按 UG571 配置 DCI_CASCADE, 例如:
# set_property DCI_CASCADE {62} [get_iobanks <已接 VRP 的 bank 号>]
# ---------------------------------------------------------------------------
