# ============================================================
# VU13P MIPI 相机验证平台 工程/BD 一键构建
# 用法: vivado -mode batch -source create_project.tcl
# 产物: ../vivado/mipi_vu13p.xpr, BD=mipi_platform, Top=mipi_platform_wrapper
# 参照 spec §5 (docs/specs/2026-06-12-vu13p-camera-validation-design.md)
# ============================================================

set script_dir [file dirname [file normalize [info script]]]
set fpga_dir   [file dirname $script_dir]
set proj_dir   "$fpga_dir/vivado"
set part       xcvu13p-fhga2104-2-i

create_project mipi_vu13p $proj_dir -part $part -force

# 自写 RTL 与板级约束
add_files -norecurse "$fpga_dir/rtl/axis_uram_framebuf.v"
add_files -fileset constrs_1 -norecurse "$fpga_dir/constraints/vu13p_pins.xdc"
update_compile_order -fileset sources_1

# ---------------- Block Design ----------------
create_bd_design mipi_platform

# --- 时钟: 19.2 MHz 单端 -> MMCM -> 100 MHz (AXI/video/lite) + 200 MHz (dphy ref)
set clk_wiz_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz clk_wiz_0]
set_property -dict [list \
    CONFIG.PRIM_SOURCE {Single_ended_clock_capable_pin} \
    CONFIG.PRIM_IN_FREQ {19.200} \
    CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {100.000} \
    CONFIG.CLKOUT2_USED {true} \
    CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {200.000} \
    CONFIG.USE_LOCKED {true} \
    CONFIG.USE_RESET {false} \
] $clk_wiz_0
create_bd_port -dir I -type clk -freq_hz 19200000 pad_clk_19m2
connect_bd_net [get_bd_ports pad_clk_19m2] [get_bd_pins clk_wiz_0/clk_in1]

# --- MicroBlaze V + 128KB LMB + MDM + proc_sys_reset + AXI互联 + INTC (Block Automation)
create_bd_cell -type ip -vlnv xilinx.com:ip:microblaze_riscv microblaze_0
apply_bd_automation -rule xilinx.com:bd_rule:microblaze_riscv -config { \
    local_mem {128KB} ecc {None} cache {None} debug_module {Debug Enabled} \
    axi_periph {Enabled} axi_intc {1} clk {/clk_wiz_0/clk_out1 (100 MHz)} } \
    [get_bd_cells microblaze_0]

# MB automation 已连接 clk_wiz_0/locked -> dcm_locked; 无板级复位, ext_reset_in 接常量。
# 注意: MB automation 把 proc_sys_reset 的 ext_reset 设成低有效 (C_EXT_RESET_HIGH=0),
# 故"不复位"必须接常量 1 (接 0 = 永久复位, peripheral_aresetn 永不放开)。
set xlconstant_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant xlconstant_0]
set_property -dict [list CONFIG.CONST_VAL {1} CONFIG.CONST_WIDTH {1}] $xlconstant_0
set rst_cell [get_bd_cells -filter {VLNV =~ "*proc_sys_reset*"}]
if {[llength [get_bd_nets -quiet -of_objects [get_bd_pins $rst_cell/ext_reset_in]]] == 0} {
    connect_bd_net [get_bd_pins xlconstant_0/dout] [get_bd_pins $rst_cell/ext_reset_in]
}

# --- AXI UART Lite 230400
set axi_uartlite_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_uartlite axi_uartlite_0]
set_property -dict [list CONFIG.C_BAUDRATE {230400}] $axi_uartlite_0
create_bd_port -dir O o_uart_tx
create_bd_port -dir I i_uart_rx
connect_bd_net [get_bd_pins axi_uartlite_0/tx] [get_bd_ports o_uart_tx]
connect_bd_net [get_bd_ports i_uart_rx] [get_bd_pins axi_uartlite_0/rx]

# --- AXI GPIO 0: CH1 4-bit 三态 (bit0 RESET, bit1 PWDN, bit2 SCL, bit3 SDA); CH2 1-bit 输入 VSYNC
set axi_gpio_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_0]
set_property -dict [list \
    CONFIG.C_GPIO_WIDTH {4} \
    CONFIG.C_IS_DUAL {1} \
    CONFIG.C_GPIO2_WIDTH {1} \
    CONFIG.C_ALL_INPUTS_2 {1} \
] $axi_gpio_0
create_bd_intf_port -mode Master -vlnv xilinx.com:interface:gpio_rtl:1.0 cam_gpio
connect_bd_intf_net [get_bd_intf_ports cam_gpio] [get_bd_intf_pins axi_gpio_0/GPIO]
create_bd_port -dir I -from 0 -to 0 cam_vsync
connect_bd_net [get_bd_ports cam_vsync] [get_bd_pins axi_gpio_0/gpio2_io_i]

# --- AXI GPIO 1: LED 8-bit 全输出
set axi_gpio_1 [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio axi_gpio_1]
set_property -dict [list CONFIG.C_GPIO_WIDTH {8} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000001}] $axi_gpio_1
create_bd_port -dir O -from 7 -to 0 pad_output_d
connect_bd_net [get_bd_pins axi_gpio_1/gpio_io_o] [get_bd_ports pad_output_d]

# --- MIPI CSI-2 RX Subsystem: 2-Lane RAW10, VFB关, 1400 Mbps, Bank 62
set mipi_csi2_rx_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:mipi_csi2_rx_subsystem mipi_csi2_rx_0]
set mipi_base_cfg [list \
    CONFIG.CMN_NUM_LANES {2} \
    CONFIG.CMN_PXL_FORMAT {RAW10} \
    CONFIG.CMN_NUM_PIXELS {1} \
    CONFIG.CMN_INC_VFB {false} \
    CONFIG.DPY_LINE_RATE {1400} \
    CONFIG.SupportLevel {1} \
    CONFIG.HP_IO_BANK_SELECTION {62} \
]
set_property -dict $mipi_base_cfg $mipi_csi2_rx_0
# Pin Assignment 须先选 clock lane 再选 data lane (PG232); 参数名 CLK_LANE_IO_LOC
set_property CONFIG.CLK_LANE_IO_LOC {AY37} $mipi_csi2_rx_0
set_property CONFIG.DATA_LANE0_IO_LOC {AY38} $mipi_csi2_rx_0
set_property CONFIG.DATA_LANE1_IO_LOC {BC35} $mipi_csi2_rx_0
# 配引脚后 IP 会自动 export 为 mipi_phy_if_1 等; 统一重命名为 mipi_phy_if
set mipi_phy_port [get_bd_intf_ports -quiet mipi_phy_if]
if {$mipi_phy_port eq ""} {
    set mipi_phy_port [get_bd_intf_ports -quiet -filter {NAME =~ "mipi_phy_if_*"}]
}
if {$mipi_phy_port eq ""} {
    make_bd_intf_pins_external [get_bd_intf_pins mipi_csi2_rx_0/mipi_phy_if]
    set mipi_phy_port [get_bd_intf_ports -quiet -filter {NAME =~ "mipi_phy_if_*"}]
}
if {$mipi_phy_port ne ""} {
    set_property name mipi_phy_if $mipi_phy_port
}
# HP IO native D-PHY 需要导出辅助 bitslice 管脚 (strobe propagation), 否则 IP XDC 的
# PACKAGE_PIN 无法落到 top port, Place 30-687 / Netlist 29-160。板外不接, LOC 由 IP 生成。
foreach bg_pin {bg0_pin0_nc bg1_pin0_nc} {
    set pin [get_bd_pins -quiet mipi_csi2_rx_0/$bg_pin]
    if {$pin ne "" && [get_bd_ports -quiet $bg_pin] eq ""} {
        make_bd_pins_external $pin
    }
}
# 时钟/复位
connect_bd_net [get_bd_pins clk_wiz_0/clk_out2] [get_bd_pins mipi_csi2_rx_0/dphy_clk_200M]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins mipi_csi2_rx_0/video_aclk]
connect_bd_net [get_bd_pins $rst_cell/peripheral_aresetn] [get_bd_pins mipi_csi2_rx_0/video_aresetn]

# --- URAM 帧缓冲 (复用RTL, Add Module), 1 MiB
set u_framebuf [create_bd_cell -type module -reference axis_uram_framebuf u_framebuf]
set_property CONFIG.FRAMEBUF_BYTES {1048576} $u_framebuf
# RX video_out 直连 framebuf 写端口 (同 100MHz 域)
connect_bd_intf_net [get_bd_intf_pins mipi_csi2_rx_0/video_out] [get_bd_intf_pins u_framebuf/s_axis]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins u_framebuf/s_axis_aclk]
connect_bd_net [get_bd_pins $rst_cell/peripheral_aresetn] [get_bd_pins u_framebuf/s_axis_aresetn]

# --- AXI-Lite 从设备挂载 (Connection Automation)
foreach slave { axi_uartlite_0/S_AXI axi_gpio_0/S_AXI axi_gpio_1/S_AXI \
                mipi_csi2_rx_0/csirxss_s_axi u_framebuf/s_axi } {
    apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
        Clk_master {/clk_wiz_0/clk_out1} Clk_slave {Auto} Clk_xbar {Auto} \
        Master {/microblaze_0 (Periph)} Slave "/$slave" ddr_seg {Auto} \
        intc_ip {/microblaze_0_axi_periph} master_apm {0}] \
        [get_bd_intf_pins $slave]
}

# --- 中断: UART + frame_done + CSI IRQ -> INTC -> MB
set concat_cell [get_bd_cells -filter {VLNV =~ "*xlconcat*"}]
set_property CONFIG.NUM_PORTS {3} $concat_cell
connect_bd_net [get_bd_pins axi_uartlite_0/interrupt]      [get_bd_pins $concat_cell/In0]
connect_bd_net [get_bd_pins u_framebuf/frame_done]         [get_bd_pins $concat_cell/In1]
connect_bd_net [get_bd_pins mipi_csi2_rx_0/csirxss_csi_irq] [get_bd_pins $concat_cell/In2]

# --- System ILA: 关键信号在线观测 (硬件 Hardware Manager 看波形)
# 采样时钟 clk_out1 (100MHz; video_aclk / lite_aclk / AXI-Lite 同域)。
#   SLOT0 AXIS : video_out 数据通路 (tdata/tvalid/tready/tlast/tuser[0]=SOF)
#   SLOT1 AXI  : u_framebuf/s_axi    固件 ARM/DONE/BYTES 读写 (控制路径)
#   SLOT2 AXI  : csirxss_s_axi       固件配置 CSI-2 RX
#   probe0 frame_done           一帧抓完
#   probe1 csirxss_csi_irq      CSI 错误/中断
#   probe2 clk locked           系统 MMCM 锁定
#   probe3 cam_vsync            sensor 出帧
#   probe4 pll_lock_out         D-PHY PLL 锁定 (MIPI 物理层起来没)
#   probe5 frame_rcvd_pulse_out PHY 层收到一帧 (脉冲)
#   probe6 system_rst_out       CSI 子系统复位状态
#   probe7 peripheral_aresetn   外设复位 (高=放开)
#   probe8 irq_vector[2:0]      {csi,frame_done,uart} -> INTC
# 三层帧视图: cam_vsync -> frame_rcvd_pulse_out -> frame_done。
# pll_lock_out/frame_rcvd_pulse_out 跨 rxbyteclkhs 域, 窄脉冲可能漏采, 仅作状态观测。
set system_ila_0 [create_bd_cell -type ip -vlnv xilinx.com:ip:system_ila system_ila_0]
set_property -dict [list \
    CONFIG.C_MON_TYPE {MIX} \
    CONFIG.C_NUM_MONITOR_SLOTS {3} \
    CONFIG.C_SLOT_0_INTF_TYPE {xilinx.com:interface:axis_rtl:1.0} \
    CONFIG.C_SLOT_1_INTF_TYPE {xilinx.com:interface:aximm_rtl:1.0} \
    CONFIG.C_SLOT_2_INTF_TYPE {xilinx.com:interface:aximm_rtl:1.0} \
    CONFIG.C_NUM_OF_PROBES {9} \
    CONFIG.C_PROBE8_WIDTH {3} \
    CONFIG.C_DATA_DEPTH {4096} \
    CONFIG.C_INPUT_PIPE_STAGES {1} \
] $system_ila_0
connect_bd_intf_net [get_bd_intf_pins mipi_csi2_rx_0/video_out]     [get_bd_intf_pins system_ila_0/SLOT_0_AXIS]
connect_bd_intf_net [get_bd_intf_pins u_framebuf/s_axi]             [get_bd_intf_pins system_ila_0/SLOT_1_AXI]
connect_bd_intf_net [get_bd_intf_pins mipi_csi2_rx_0/csirxss_s_axi] [get_bd_intf_pins system_ila_0/SLOT_2_AXI]
connect_bd_net [get_bd_pins u_framebuf/frame_done]              [get_bd_pins system_ila_0/probe0]
connect_bd_net [get_bd_pins mipi_csi2_rx_0/csirxss_csi_irq]     [get_bd_pins system_ila_0/probe1]
connect_bd_net [get_bd_pins clk_wiz_0/locked]                   [get_bd_pins system_ila_0/probe2]
connect_bd_net [get_bd_ports cam_vsync]                         [get_bd_pins system_ila_0/probe3]
connect_bd_net [get_bd_pins mipi_csi2_rx_0/pll_lock_out]        [get_bd_pins system_ila_0/probe4]
connect_bd_net [get_bd_pins mipi_csi2_rx_0/frame_rcvd_pulse_out] [get_bd_pins system_ila_0/probe5]
connect_bd_net [get_bd_pins mipi_csi2_rx_0/system_rst_out]      [get_bd_pins system_ila_0/probe6]
connect_bd_net [get_bd_pins $rst_cell/peripheral_aresetn]      [get_bd_pins system_ila_0/probe7]
connect_bd_net [get_bd_pins $concat_cell/dout]                  [get_bd_pins system_ila_0/probe8]
connect_bd_net [get_bd_pins clk_wiz_0/clk_out1]            [get_bd_pins system_ila_0/clk]
connect_bd_net [get_bd_pins $rst_cell/peripheral_aresetn] [get_bd_pins system_ila_0/resetn]

# --- 地址映射: framebuf 固定 0x8000_0000 / 32M (hw_defs.h 硬编码, 不可改)
assign_bd_address
set fb_seg [get_bd_addr_segs -of_objects [get_bd_addr_spaces microblaze_0/Data] -filter {NAME =~ "*u_framebuf*"}]
set_property range  32M        $fb_seg
set_property offset 0x80000000 $fb_seg

validate_bd_design
# 关闭分层 OOC checkpoint, 避免 Generate Block Design 触发大量 *_synth_1 OOC 任务
set_property synth_checkpoint_mode None [get_files mipi_platform.bd]
save_bd_design

# --- Wrapper 作为 Top
make_wrapper -files [get_files mipi_platform.bd] -top
add_files -norecurse "$proj_dir/mipi_vu13p.gen/sources_1/bd/mipi_platform/hdl/mipi_platform_wrapper.v"
set_property top mipi_platform_wrapper [current_fileset]
update_compile_order -fileset sources_1

# 只生成 HDL/sim/synthesis 产物, 不跑 OOC synth (等价于 GUI Generate without OOC)
generate_target {synthesis} [get_files mipi_platform.bd] -force
export_ip_user_files -of_objects [get_files mipi_platform.bd] -no_script -sync -force -quiet

puts "=== BD BUILD OK ==="
puts "NOTE: synth_checkpoint_mode=None; 顶层综合请单独 Run Synthesis (synth_1), 勿对 BD 再点 Generate Target=all"
