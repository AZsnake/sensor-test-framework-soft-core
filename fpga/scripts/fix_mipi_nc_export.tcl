# ============================================================
# 修复: MIPI CSI-2 RX 换脚后 bgX_pin0_nc 丢失顶层端口导致
#   [Netlist 29-160] PACKAGE_PIN/DATA_RATE not exist for type 'pin'
#   [Place 30-687]   RX_BS[0]/RX_BS[26] 找不到关联 I/O
# 原因: lane LOC 改动后 byte group 由 bg0+bg1 变为 bg0+bg2,
#   旧的 bg1_pin0_nc_0 顶层端口消失,新的 bg2_pin0_nc 未引出,
#   两个 NC 脚都变成内部未连接 -> bitslice 无 I/O site。
# 处理: 把 bg0_pin0_nc / bg2_pin0_nc 重新 make external,
#   IP 自身 XDC 会把它们钉到 BC34 / AY37 (Bank 62);
#   IOSTANDARD 由 vu13p_pins.xdc 里的 LVCMOS12 覆盖 (避免默认 LVCMOS18 撞 1.2V)。
# 在 Vivado Tcl Console 中 source (工程须已打开)。
# ============================================================

set bd_name mipi_platform
set cell    /mipi_csi2_rx_0

# 1. 打开 BD
if {[catch {current_bd_design} _]} {
    open_bd_design [get_files ${bd_name}.bd]
}
current_bd_design [get_bd_designs ${bd_name}]

# 2. 逐个 NC 脚: 若尚未引出顶层则 make external
foreach {pin port} {bg0_pin0_nc bg0_pin0_nc_0  bg2_pin0_nc bg2_pin0_nc_0} {
    set bp [get_bd_pins -quiet ${cell}/${pin}]
    if {$bp eq ""} {
        puts "WARN: 找不到 IP 引脚 ${cell}/${pin},请核对当前 byte group 配置"
        continue
    }
    # 已连接到外部端口就跳过
    set ext [get_bd_ports -quiet -of_objects [get_bd_nets -quiet -of_objects $bp]]
    if {$ext ne ""} {
        puts "OK : ${pin} 已是外部端口 ([get_property NAME $ext]),跳过"
        continue
    }
    make_bd_pins_external -name $port $bp
    puts "FIX: ${pin} -> 顶层端口 ${port}"
}

# 3. 校验 + 保存
validate_bd_design
save_bd_design

# 4. 重新生成产物 (wrapper 会新增 bg0_pin0_nc_0 / bg2_pin0_nc_0 顶层端口)
reset_target   all [get_files ${bd_name}.bd]
generate_target all [get_files ${bd_name}.bd]

puts "=== 完成: 记得确认 vu13p_pins.xdc 里两个 NC 脚的 LVCMOS12 约束已就位,再重综合 ==="
