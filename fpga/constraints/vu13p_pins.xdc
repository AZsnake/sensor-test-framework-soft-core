# ============================================================
# VU13P MIPI 相机验证平台 板级管脚约束
# 器件: xcvu13p-fhga2104-2-i
# create_clock 由 BD/clk_wiz 自动生成,勿在此手写 (18-1055)
# ============================================================

# 系统时钟 19.2 MHz (Bank 63, GC_QBC 全局时钟脚)
set_property -dict {PACKAGE_PIN AL32 IOSTANDARD LVCMOS18} [get_ports pad_clk_19m2]

# UART (Bank 66)
set_property -dict {PACKAGE_PIN BA16 IOSTANDARD LVCMOS18} [get_ports o_uart_tx]
set_property -dict {PACKAGE_PIN BA14 IOSTANDARD LVCMOS18} [get_ports i_uart_rx]

# 相机控制 GPIO (Bank 68, AXI GPIO CH1 三态, 4-bit)
#   bit0 = RESET(XCLR)  bit1 = PWDN  bit2 = I2C SCL  bit3 = I2C SDA
set_property -dict {PACKAGE_PIN L34 IOSTANDARD LVCMOS18} [get_ports {cam_gpio_tri_io[0]}]
set_property -dict {PACKAGE_PIN L35 IOSTANDARD LVCMOS18} [get_ports {cam_gpio_tri_io[1]}]
# I2C 开漏 bit-bang: 释放(TRI=1)后须靠上拉拉高; 板级若无外部电阻则启用 FPGA 弱上拉
# (内部约 50kΩ, bring-up 可用; 正式联调仍建议板载 2.2k~4.7k 至 1.8V/3.3V I2C 域)
set_property -dict {PACKAGE_PIN L33 IOSTANDARD LVCMOS18 PULLUP true} [get_ports {cam_gpio_tri_io[2]}]
set_property -dict {PACKAGE_PIN K34 IOSTANDARD LVCMOS18 PULLUP true} [get_ports {cam_gpio_tri_io[3]}]

# 相机 VSYNC 输入 (Bank 68, AXI GPIO CH2)
set_property -dict {PACKAGE_PIN M35 IOSTANDARD LVCMOS18} [get_ports {cam_vsync[0]}]

# LED 跑马灯 (Bank 69)
set_property -dict {PACKAGE_PIN J35 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[0]}]
set_property -dict {PACKAGE_PIN H34 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[1]}]
set_property -dict {PACKAGE_PIN H35 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[2]}]
set_property -dict {PACKAGE_PIN G35 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[3]}]
set_property -dict {PACKAGE_PIN F34 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[4]}]
set_property -dict {PACKAGE_PIN F35 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[5]}]
set_property -dict {PACKAGE_PIN E34 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[6]}]
set_property -dict {PACKAGE_PIN D34 IOSTANDARD LVCMOS18} [get_ports {pad_output_d[7]}]

# ------------------------------------------------------------
# MIPI CSI-2 RX (Bank 62, MIPI_DPHY_DCI, VCCO=1.2V)
# 引脚 LOC 由 MIPI CSI-2 RX Subsystem IP 的 Pin Assignment 生成
# (CLK=AY37/BA37 候选1, D0=AY38/AY39=LA25, D1=BC35/BC36=LA29)
# 辅助 bitslice 管脚 bg0_pin0_nc(BC34)/bg1_pin0_nc(BE40) 须 export 到顶层,板外不接
# 此处不重复 LOC,避免与 IP XDC 冲突;P0 闭环后核对 IP 生成值
# 若 Bank 62 VRP 未接 240Ω 而同列其它 bank 已接,放开下行:
# set_property DCI_CASCADE {62} [get_iobanks <已接VRP的bank>]
# ------------------------------------------------------------
