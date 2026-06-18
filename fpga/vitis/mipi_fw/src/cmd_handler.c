// fpga/vitis-app/mipi_fw/src/cmd_handler.c
#include "cmd_handler.h"
#include "hw_defs.h"
#include "image_tx.h"
#include "sensor.h"
#include "xil_io.h"
#include "xgpio.h"
#include "sleep.h"
#include "i2c_bitbang.h"

extern XGpio gpio_inst;

static volatile int busy = 0;

// ECC/CRC 误码累计: RX Subsystem ISR 为 sticky 位(write-1-clear), 固件轮询折算成计数
static uint16_t ecc_err_count = 0;
static uint16_t crc_err_count = 0;

static void csi_poll_errors(void) {
    uint32_t isr = Xil_In32(CSIRX_BASEADDR + CSIRX_ISR_OFFSET);
    uint32_t clr = 0;
    if (isr & CSIRX_ISR_ECC1BERR_MASK) { ecc_err_count++; clr |= CSIRX_ISR_ECC1BERR_MASK; }
    if (isr & CSIRX_ISR_ECC2BERR_MASK) { ecc_err_count++; clr |= CSIRX_ISR_ECC2BERR_MASK; }
    if (isr & CSIRX_ISR_CRCERR_MASK)   { crc_err_count++; clr |= CSIRX_ISR_CRCERR_MASK; }
    if (clr)
        Xil_Out32(CSIRX_BASEADDR + CSIRX_ISR_OFFSET, clr);
}

void cmd_handler_init(void) {
    // CSI-2 RX 中断接在 INTC bit2, 但固件对误码走轮询(csi_poll_errors), 不用中断。
    // sensor 出流后 CSI 会拉起中断输出 -> 无 handler 清除 -> 开全局中断即风暴。
    // 在源头屏蔽: GIER=0(关中断输出)+ IER=0(关各路使能), 并清掉残留 ISR sticky 位。
    Xil_Out32(CSIRX_BASEADDR + CSIRX_GIER_OFFSET, 0);
    Xil_Out32(CSIRX_BASEADDR + CSIRX_IER_OFFSET, 0);
    Xil_Out32(CSIRX_BASEADDR + CSIRX_ISR_OFFSET,
              CSIRX_ISR_ECC1BERR_MASK | CSIRX_ISR_ECC2BERR_MASK | CSIRX_ISR_CRCERR_MASK);

    // 使能 CSI-2 RX core (PG232 CCR bit0)
    Xil_Out32(CSIRX_BASEADDR + CSIRX_CCR_OFFSET, CSIRX_CCR_COREENB_MASK);
    ecc_err_count = 0;
    crc_err_count = 0;
}

static void cmd_write_reg(const frame_t *f) {
    if (f->len != 3) { send_err(ERR_INVALID_PARAM); return; }
    uint8_t tx_buf[3] = {f->payload[0], f->payload[1], f->payload[2]};

    int status = i2c_write(IMX298_I2C_ADDR, tx_buf, 3);
    if (status != I2C_OK) {
        send_err(ERR_I2C_NACK);
        return;
    }
    send_ack(CMD_WRITE_REG);
}

static void cmd_read_reg(const frame_t *f) {
    if (f->len != 2) { send_err(ERR_INVALID_PARAM); return; }
    uint8_t addr_buf[2] = {f->payload[0], f->payload[1]};
    uint8_t data;

    int status = i2c_write_read(IMX298_I2C_ADDR, addr_buf, 2, &data, 1);
    if (status != I2C_OK) {
        send_err(ERR_I2C_NACK);
        return;
    }

    send_response(CMD_READ_REG, &data, 1);
}

static void cmd_read_status(const frame_t *f) {
    (void)f;
    uint8_t resp[8];

    csi_poll_errors();
    // LinkUp: 时钟 lane 退出 Stop 态 = 进入 HS (xcsi_hw.h CLKINFR bit1)
    uint32_t clkinfo = Xil_In32(CSIRX_BASEADDR + CSIRX_CLKINFR_OFFSET);
    uint32_t port   = 0;                // 单端口固定 0
    uint32_t rate   = DPHY_RATE_MBPS;
    uint32_t ecc    = ecc_err_count;
    uint32_t crc    = crc_err_count;
    uint32_t linkup = (clkinfo & CSIRX_CLKINFR_STOP_MASK) ? 0 : 1;

    resp[0] = (uint8_t)port;
    resp[1] = (uint8_t)(rate >> 8);
    resp[2] = (uint8_t)(rate & 0xFF);
    resp[3] = (uint8_t)(ecc >> 8);
    resp[4] = (uint8_t)(ecc & 0xFF);
    resp[5] = (uint8_t)(crc >> 8);
    resp[6] = (uint8_t)(crc & 0xFF);
    resp[7] = (uint8_t)linkup;

    send_response(CMD_READ_STATUS, resp, 8);
}

static void cmd_gpio_ctrl(const frame_t *f) {
    if (f->len != 2) { send_err(ERR_INVALID_PARAM); return; }
    uint8_t pin = f->payload[0];
    uint8_t level = f->payload[1];
    // VU13P: bit0=RESET, bit1=PWDN; bit2/3 是 I2C SCL/SDA, 由 i2c_bitbang 独占, 禁止 0x05 触碰
    if (pin > 1) { send_err(ERR_INVALID_PARAM); return; }

    uint32_t val = XGpio_DiscreteRead(&gpio_inst, 1);
    if (level)
        val |= (1 << pin);
    else
        val &= ~(1 << pin);
    XGpio_DiscreteWrite(&gpio_inst, 1, val);
    send_ack(CMD_GPIO_CTRL);
}

static void cmd_reset_seq(const frame_t *f) {
    (void)f;
    sensor_reset();
    send_ack(CMD_RESET_SEQ);
}

static void cmd_set_source(const frame_t *f) {
    // 数据源只有相机(0); 1/2 回 ERR — 保持上位机协议兼容 (spec §8.2)
    if (f->len != 1 || f->payload[0] != 0) { send_err(ERR_INVALID_PARAM); return; }
    send_ack(CMD_SET_SOURCE);
}

static void cmd_set_port(const frame_t *f) {
    // 单端口: 任意合法 payload 直接 ACK, 不动作 (spec §8.2)
    if (f->len != 1 || f->payload[0] > 3) { send_err(ERR_INVALID_PARAM); return; }
    send_ack(CMD_SET_PORT);
}

// Lane 诊断: 只读 dump CSI-2 RX 子系统 6 个状态寄存器, 用于定位哪条 lane 不同步。
// 顺序: CCR(0x00) CSR(0x10) ISR(0x24) ClkLane(0x3C) Lane0(0x40) Lane1(0x44), 各 u32 大端。
// 只读不清 ISR(write-1-clear), 保留 sticky 误码位供判读。
static void cmd_lane_diag(const frame_t *f) {
    (void)f;
    static const uint16_t offs[6] = {
        CSIRX_CCR_OFFSET, CSIRX_CSR_OFFSET, CSIRX_ISR_OFFSET,
        CSIRX_CLKINFR_OFFSET, CSIRX_L0INFR_OFFSET, CSIRX_L1INFR_OFFSET,
    };
    uint8_t resp[24];
    for (int i = 0; i < 6; i++) {
        uint32_t v = Xil_In32(CSIRX_BASEADDR + offs[i]);
        resp[i * 4 + 0] = (uint8_t)(v >> 24);
        resp[i * 4 + 1] = (uint8_t)(v >> 16);
        resp[i * 4 + 2] = (uint8_t)(v >> 8);
        resp[i * 4 + 3] = (uint8_t)(v);
    }
    send_response(CMD_LANE_DIAG, resp, 24);
}

// 在线读写 D-PHY HS_SETTLE (L0+L1), 用于 bring-up 期扫描 HS 采样窗口。
// payload: u16 大端目标值; 0xFFFF = 只读回探(不写, 供客户端自校准 ns/LSB)。
// 响应 4 字节: L0(u16 大端) L1(u16 大端) 回读值。
// 注意: 需 bit流 build 时 DPY_EN_REG_IF=true; 否则 D-PHY 寄存器块不存在, 回读恒 0。
// HS_SETTLE 写后于下一次 HS 进入(下一行)生效, 流式下无需软复位。
static void cmd_set_hs_settle(const frame_t *f) {
    if (f->len != 2) { send_err(ERR_INVALID_PARAM); return; }
    uint16_t val = ((uint16_t)f->payload[0] << 8) | f->payload[1];
    uint32_t a0 = CSIRX_BASEADDR + CSIRX_DPHY_OFFSET + DPHY_HSSETTLE_L0_OFFSET;
    uint32_t a1 = CSIRX_BASEADDR + CSIRX_DPHY_OFFSET + DPHY_HSSETTLE_L1_OFFSET;
    if (val != 0xFFFF) {
        if (val > DPHY_HSSETTLE_MASK) { send_err(ERR_INVALID_PARAM); return; }
        Xil_Out32(a0, val);
        Xil_Out32(a1, val);
    }
    uint16_t r0 = (uint16_t)(Xil_In32(a0) & DPHY_HSSETTLE_MASK);
    uint16_t r1 = (uint16_t)(Xil_In32(a1) & DPHY_HSSETTLE_MASK);
    uint8_t resp[4] = { (uint8_t)(r0 >> 8), (uint8_t)r0,
                        (uint8_t)(r1 >> 8), (uint8_t)r1 };
    send_response(CMD_SET_HS_SETTLE, resp, 4);
}

// 只读 dump D-PHY 子块状态寄存器, 信息比 CSI 控制器 CLKINFR/LxINFR 丰富:
// 每 lane 的 Mode/InitDone/HSAbort/CalibComplete/Stop + per-lane 包计数。
// 顺序: CTRL(0x00) CLSTATUS(0x18) DL0(0x1C) DL1(0x20) HSSETTLE_L0(0x30) HSSETTLE_L1(0x48), 各 u32 大端。
// 需 bit流 build 时 DPY_EN_REG_IF=true, 否则全 0。
static void cmd_dphy_diag(const frame_t *f) {
    (void)f;
    static const uint16_t offs[6] = {
        DPHY_CTRL_OFFSET, DPHY_CLSTATUS_OFFSET,
        DPHY_DL0STATUS_OFFSET, DPHY_DL1STATUS_OFFSET,
        DPHY_HSSETTLE_L0_OFFSET, DPHY_HSSETTLE_L1_OFFSET,
    };
    uint8_t resp[24];
    for (int i = 0; i < 6; i++) {
        uint32_t v = Xil_In32(CSIRX_BASEADDR + CSIRX_DPHY_OFFSET + offs[i]);
        resp[i * 4 + 0] = (uint8_t)(v >> 24);
        resp[i * 4 + 1] = (uint8_t)(v >> 16);
        resp[i * 4 + 2] = (uint8_t)(v >> 8);
        resp[i * 4 + 3] = (uint8_t)(v);
    }
    send_response(CMD_DPHY_DIAG, resp, 24);
}

static void cmd_clr_err(const frame_t *f) {
    (void)f;
    ecc_err_count = 0;
    crc_err_count = 0;
    // 同步清掉 ISR 中尚未折算的误码 sticky 位
    Xil_Out32(CSIRX_BASEADDR + CSIRX_ISR_OFFSET,
              CSIRX_ISR_ECC1BERR_MASK | CSIRX_ISR_ECC2BERR_MASK | CSIRX_ISR_CRCERR_MASK);
    send_ack(CMD_CLR_ERR);
}

void cmd_dispatch(const frame_t *frame) {
    if (busy && frame->cmd != CMD_READ_STATUS) {
        send_err(ERR_BUSY);
        return;
    }
    switch (frame->cmd) {
    case CMD_WRITE_REG:   cmd_write_reg(frame);   break;
    case CMD_READ_REG:    cmd_read_reg(frame);     break;
    case CMD_READ_STATUS: cmd_read_status(frame);  break;
    case CMD_CAPTURE: {
        if (frame->len != 5) { send_err(ERR_INVALID_PARAM); break; }
        uint16_t w = ((uint16_t)frame->payload[1] << 8) | frame->payload[2];
        uint16_t h = ((uint16_t)frame->payload[3] << 8) | frame->payload[4];
        send_ack(CMD_CAPTURE);
        busy = 1;
        if (capture_and_send(w, h) != 0)
            send_err(ERR_VDMA_FAIL);
        busy = 0;
        break;
    }
    case CMD_GPIO_CTRL:   cmd_gpio_ctrl(frame);    break;
    case CMD_RESET_SEQ:   cmd_reset_seq(frame);    break;
    case CMD_SET_SOURCE:  cmd_set_source(frame);   break;
    case CMD_SET_PORT:    cmd_set_port(frame);     break;
    case CMD_CLR_ERR:     cmd_clr_err(frame);      break;
    case CMD_LANE_DIAG:   cmd_lane_diag(frame);    break;
    case CMD_SET_HS_SETTLE: cmd_set_hs_settle(frame); break;
    case CMD_DPHY_DIAG:   cmd_dphy_diag(frame);    break;
    default:              send_err(ERR_INVALID_CMD); break;
    }
}
