// fpga/vitis-app/mipi_fw/src/i2c_bitbang.c
//
// GPIO bit-bang I2C master (open-drain via AXI GPIO tri-state control).
//
// AXI GPIO register map (channel 1):
//   GPIO_DATA  (0x0000) — output data register
//   GPIO_TRI   (0x0004) — tri-state control (1 = input/high-Z, 0 = output)
//
// Open-drain emulation:
//   Pull low:  TRI bit = 0, DATA bit = 0  →  drives 0
//   Release:   TRI bit = 1                 →  high-Z, external 4.7k pulls high
//   Read pin:  set TRI bit = 1, then read GPIO_DATA for input value

#include "i2c_bitbang.h"
#include "hw_defs.h"
#include "xil_io.h"
#include "sleep.h"

#define GPIO_DATA_REG  (GPIO_BASEADDR + 0x0000)
#define GPIO_TRI_REG   (GPIO_BASEADDR + 0x0004)

// 100 kHz (match reference sens_imx298_i2c_init); half-period ~5 us
#define I2C_DELAY_US   5

static inline void i2c_delay(void) {
    usleep(I2C_DELAY_US);
}

// --- Low-level pin control ---

static inline void scl_low(void) {
    uint32_t tri = Xil_In32(GPIO_TRI_REG);
    uint32_t dat = Xil_In32(GPIO_DATA_REG);
    dat &= ~GPIO_I2C_SCL;
    Xil_Out32(GPIO_DATA_REG, dat);
    tri &= ~GPIO_I2C_SCL;   // drive output
    Xil_Out32(GPIO_TRI_REG, tri);
}

static inline void scl_release(void) {
    uint32_t tri = Xil_In32(GPIO_TRI_REG);
    tri |= GPIO_I2C_SCL;    // high-Z → pulled high
    Xil_Out32(GPIO_TRI_REG, tri);
}

static inline void sda_low(void) {
    uint32_t tri = Xil_In32(GPIO_TRI_REG);
    uint32_t dat = Xil_In32(GPIO_DATA_REG);
    dat &= ~GPIO_I2C_SDA;
    Xil_Out32(GPIO_DATA_REG, dat);
    tri &= ~GPIO_I2C_SDA;
    Xil_Out32(GPIO_TRI_REG, tri);
}

static inline void sda_release(void) {
    uint32_t tri = Xil_In32(GPIO_TRI_REG);
    tri |= GPIO_I2C_SDA;
    Xil_Out32(GPIO_TRI_REG, tri);
}

static inline int scl_read(void) {
    scl_release();
    i2c_delay();
    uint32_t val = Xil_In32(GPIO_DATA_REG);
    return (val & GPIO_I2C_SCL) ? 1 : 0;
}

static inline int sda_read(void) {
    sda_release();
    i2c_delay();
    uint32_t val = Xil_In32(GPIO_DATA_REG);
    return (val & GPIO_I2C_SDA) ? 1 : 0;
}

// --- I2C primitives ---

static void i2c_start(void) {
    // SDA high, SCL high (both released), then SDA low while SCL high
    sda_release();
    scl_release();
    i2c_delay();
    sda_low();
    i2c_delay();
    scl_low();
    i2c_delay();
}

static void i2c_stop(void) {
    sda_low();
    i2c_delay();
    scl_release();
    i2c_delay();
    sda_release();
    i2c_delay();
}

static void i2c_restart(void) {
    sda_release();
    i2c_delay();
    scl_release();
    i2c_delay();
    sda_low();
    i2c_delay();
    scl_low();
    i2c_delay();
}

// Send one byte, return 0 if ACK received, -1 if NACK
static int i2c_send_byte(uint8_t byte) {
    for (int i = 7; i >= 0; i--) {
        if (byte & (1 << i))
            sda_release();
        else
            sda_low();
        i2c_delay();
        scl_release();
        i2c_delay();
        scl_low();
        i2c_delay();
    }

    // Read ACK: release SDA, clock, sample
    sda_release();
    i2c_delay();
    scl_release();
    i2c_delay();
    int nack = sda_read();
    scl_low();
    i2c_delay();

    return nack ? -1 : 0;
}

// Receive one byte, send ACK if `ack` is non-zero, NACK otherwise
static uint8_t i2c_recv_byte(int ack) {
    uint8_t byte = 0;
    sda_release();

    for (int i = 7; i >= 0; i--) {
        scl_release();
        i2c_delay();
        if (sda_read())
            byte |= (1 << i);
        scl_low();
        i2c_delay();
    }

    // Send ACK/NACK
    if (ack)
        sda_low();
    else
        sda_release();
    i2c_delay();
    scl_release();
    i2c_delay();
    scl_low();
    i2c_delay();
    sda_release();

    return byte;
}

// --- Public API ---

void i2c_init(void) {
    // Ensure DATA bits for SCL/SDA are 0 (so when TRI=0 they drive low)
    uint32_t dat = Xil_In32(GPIO_DATA_REG);
    dat &= ~(GPIO_I2C_SCL | GPIO_I2C_SDA);
    Xil_Out32(GPIO_DATA_REG, dat);

    // Release both lines (high-Z)
    scl_release();
    sda_release();
    i2c_delay();
}

int i2c_bus_idle(uint8_t *scl, uint8_t *sda) {
    uint8_t scl_hi = (uint8_t)scl_read();
    uint8_t sda_hi = (uint8_t)sda_read();
    if (scl)
        *scl = scl_hi;
    if (sda)
        *sda = sda_hi;
    return (scl_hi && sda_hi) ? I2C_OK : I2C_NACK;
}

int i2c_probe(uint8_t addr) {
    i2c_start();
    int ack = i2c_send_byte((addr << 1) | 0);
    i2c_stop();
    return (ack == 0) ? I2C_OK : I2C_NACK;
}

int i2c_write(uint8_t addr, const uint8_t *data, uint16_t len) {
    i2c_start();

    if (i2c_send_byte((addr << 1) | 0) != 0) {
        i2c_stop();
        return I2C_NACK;
    }

    for (uint16_t i = 0; i < len; i++) {
        if (i2c_send_byte(data[i]) != 0) {
            i2c_stop();
            return I2C_NACK;
        }
    }

    i2c_stop();
    return I2C_OK;
}

int i2c_write_read(uint8_t addr, const uint8_t *wdata, uint16_t wlen,
                   uint8_t *rdata, uint16_t rlen) {
    // Write phase
    i2c_start();

    if (i2c_send_byte((addr << 1) | 0) != 0) {
        i2c_stop();
        return I2C_NACK;
    }

    for (uint16_t i = 0; i < wlen; i++) {
        if (i2c_send_byte(wdata[i]) != 0) {
            i2c_stop();
            return I2C_NACK;
        }
    }

    // Repeated start + read phase
    i2c_restart();

    if (i2c_send_byte((addr << 1) | 1) != 0) {
        i2c_stop();
        return I2C_NACK;
    }

    for (uint16_t i = 0; i < rlen; i++) {
        int ack = (i < rlen - 1) ? 1 : 0;  // NACK on last byte
        rdata[i] = i2c_recv_byte(ack);
    }

    i2c_stop();
    return I2C_OK;
}
