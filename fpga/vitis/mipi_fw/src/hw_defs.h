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
#define CSIRX_CLKINFR_OFFSET    0x3C    // Clock Lane Info

#define CSIRX_CCR_COREENB_MASK    0x00000001
#define CSIRX_CCR_SOFTRESET_MASK  0x00000002
#define CSIRX_CSR_PKTCOUNT_SHIFT  16      // CSR[31:16] = 包计数
#define CSIRX_ISR_ECC2BERR_MASK   0x00000800
#define CSIRX_ISR_ECC1BERR_MASK   0x00000400
#define CSIRX_ISR_CRCERR_MASK     0x00000200
#define CSIRX_CLKINFR_STOP_MASK   0x00000002  // 1=时钟lane处于Stop态(非HS); 0=HS → LinkUp

// D-PHY 线速率 (IP 例化固定值, 0x03 响应 Rate 字段)
#define DPHY_RATE_MBPS  1400

// URAM frame buffer (axis_uram_framebuf, BD Address Editor 固定分配)
#define FRAMEBUF_BASEADDR   0x80000000
#define FRAMEBUF_CTRL_OFF   0x01000000
#define FB_REG_ARM    (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x00)
#define FB_REG_DONE   (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x04)
#define FB_REG_BYTES  (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x08)
#define FB_REG_STATUS (FRAMEBUF_BASEADDR + FRAMEBUF_CTRL_OFF + 0x0C)

#endif
