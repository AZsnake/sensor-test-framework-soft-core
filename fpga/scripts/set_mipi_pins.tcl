# ============================================================
# 重新分配 MIPI CSI-2 RX Subsystem 的 D-PHY lane 管脚 (Bank 62)
# 目标(定稿):
#   CLK P/N = BE40 / BE41   (P=BE40, QBC)
#   D0  P/N = AY38 / AY39   (P=AY38)
#   D1  P/N = BC35 / BC36   (P=BC35)
# 说明: IP 只接受差分对的 P 脚 LOC,N 脚由相邻互补脚自动确定。
# 在 Vivado Tcl Console 中 source 本脚本 (工程须已打开)。
# ============================================================

set bd_name   mipi_platform
set cell_path /mipi_csi2_rx_0

# 1. 确保 BD 已打开
if {[catch {current_bd_design} _err]} {
    open_bd_design [get_files ${bd_name}.bd]
}
current_bd_design [get_bd_designs ${bd_name}]

# 2. 写入 lane 管脚 (只给 P 脚)
set cell [get_bd_cells ${cell_path}]
if {$cell eq ""} {
    error "找不到 BD cell ${cell_path},请确认 BD 已打开且实例名正确"
}

set_property -dict [list \
    CONFIG.CLK_LANE_IO_LOC   {BE40} \
    CONFIG.DATA_LANE0_IO_LOC {AY38} \
    CONFIG.DATA_LANE1_IO_LOC {BC35} \
] $cell

# 3. 回读确认
puts "=== 写入后的 lane LOC ==="
foreach p {CLK_LANE_IO_LOC DATA_LANE0_IO_LOC DATA_LANE1_IO_LOC \
           CLK_LANE_IO_LOC_NAME DATA_LANE0_IO_LOC_NAME DATA_LANE1_IO_LOC_NAME} {
    puts [format "  %-24s = %s" $p [get_property CONFIG.$p $cell]]
}

# 4. 校验 + 保存 + 重新生成 IP/wrapper 产物
validate_bd_design
save_bd_design

# 重新生成该 IP 的输出产物 (XDC/HDL),让新 LOC 生效
reset_target   all [get_files ${bd_name}.bd]
generate_target all [get_files ${bd_name}.bd]

puts "=== 完成: 新管脚已写入 BD 与 IP XDC,可重新跑综合/实现 ==="
