// fpga/vitis/mipi_fw/src/hw_defs.h
#ifndef HW_DEFS_H
#define HW_DEFS_H

#include "xparameters.h"

// Base addresses (from xparameters.h, verify after XSA export)
#define UART_BASEADDR      XPAR_AXI_UARTLITE_0_BASEADDR
#define GPIO_BASEADDR      XPAR_AXI_GPIO_0_BASEADDR
#define LED_GPIO_BASEADDR  XPAR_AXI_GPIO_1_BASEADDR
#if defined(XPAR_XINTC_0_BASEADDR)
#define INTC_BASEADDR      XPAR_XINTC_0_BASEADDR
#elif defined(XPAR_AXI_INTC_0_BASEADDR)
#define INTC_BASEADDR      XPAR_AXI_INTC_0_BASEADDR
#else
#error "No AXI interrupt controller base address in xparameters.h"
#endif
#define CSIRX_BASEADDR     XPAR_MIPI_CSI2_RX_0_BASEADDR

// GPIO bit mapping (AXI GPIO_0 channel 1, width 4) — VU13P 重映射
//   bit0=RESET(XCLR) L34, bit1=PWDN L35, bit2=SCL L33, bit3=SDA K34
#define GPIO_XCLR    (0 << 0) // XCLR should be low
#define GPIO_PWDN    (1 << 1)
#define GPIO_I2C_SCL (1 << 2)
#define GPIO_I2C_SDA (1 << 3)
// (无 CAM_EN 引脚; 0x05 命令仅允许 pin 0-1, SCL/SDA 由 i2c_bitbang 独占)

// IMX298 I2C address
#define IMX298_I2C_ADDR  0x1A

// UART baud
#define UART_BAUD  230400

// MIPI CSI-2 RX Subsystem 控制寄存器 (PG232, 偏移/掩码取自官方驱动 xcsi_hw.h v1.7)
// 0x03/0x0A 命令直读此处, 取代已删除的 mipi_ctrl_regs
#define CSIRX_CCR_OFFSET        0x00    // Core Configuration
#define CSIRX_CSR_OFFSET        0x10    // Core Status
#define CSIRX_GIER_OFFSET       0x20    // Global Interrupt Enable (0=屏蔽中断输出)
#define CSIRX_ISR_OFFSET        0x24    // Interrupt Status (write-1-clear)
#define CSIRX_IER_OFFSET        0x28    // Interrupt Enable
#define CSIRX_CLKINFR_OFFSET    0x3C    // Clock Lane Info  (bit1=Stop)
#define CSIRX_L0INFR_OFFSET     0x40    // Data Lane0 Info  (bit0=SoTErr bit1=SoTSyncErr bit5=Stop)
#define CSIRX_L1INFR_OFFSET     0x44    // Data Lane1 Info

#define CSIRX_CCR_COREENB_MASK    0x00000001
#define CSIRX_CCR_SOFTRESET_MASK  0x00000002
#define CSIRX_CSR_PKTCOUNT_SHIFT  16      // CSR[31:16] = 包计数
#define CSIRX_ISR_ECC2BERR_MASK   0x00000800
#define CSIRX_ISR_ECC1BERR_MASK   0x00000400
#define CSIRX_ISR_CRCERR_MASK     0x00000200
#define CSIRX_CLKINFR_STOP_MASK   0x00000002  // 1=时钟lane处于Stop态(非HS); 0=HS → LinkUp

// D-PHY 子块: 在 CSI-2 RX Subsystem 内部偏移 0x1000 (需 build 时 DPY_EN_REG_IF=true,
// 否则回读恒 0)。HS_SETTLE 寄存器偏移取自 xdphy_hw.h (per-lane, 9-bit 计数)。
#define CSIRX_DPHY_OFFSET         0x1000
#define DPHY_HSSETTLE_L0_OFFSET   0x30    // XDPHY_HSSETTLE_REG_OFFSET  (lane0)
#define DPHY_HSSETTLE_L1_OFFSET   0x48    // XDPHY_HSSETTLE1_REG_OFFSET (lane1)
#define DPHY_HSSETTLE_MASK        0x1FF   // XDPHY_HS_SETTLE_MAX_VALUE

// D-PHY 状态寄存器 (xdphy_hw.h) — 比 CSI 控制器 CLKINFR/LxINFR 详细
#define DPHY_CTRL_OFFSET          0x00    // bit0=SoftReset bit1=DphyEnable
#define DPHY_CLSTATUS_OFFSET      0x18    // 时钟lane: [1:0]Mode bit2=ULPS bit3=InitDone bit4=Stop bit5=ErrCtrl
#define DPHY_DL0STATUS_OFFSET     0x1C    // 数据lane0: bit3=InitDone bit4=HSAbort bit5=EscAbort bit6=Stop bit7=CalibDone bit8=CalibStat [31:16]=pktcount
#define DPHY_DL1STATUS_OFFSET     0x20    // 数据lane1 (同上)

// D-PHY 线速率
#define DPHY_RATE_MBPS  800

// URAM frame buffer (axis_uram_framebuf, BD Address Editor 固定分配)
#define FRAMEBUF_BASEADDR   0x80000000
#define FRAMEBUF_CTRL_OFF   0x01000000
#define FB_REG_ARM    (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x00)
#define FB_REG_DONE   (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x04)
#define FB_REG_BYTES  (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x08)
#define FB_REG_STATUS (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x0C)

#endif
