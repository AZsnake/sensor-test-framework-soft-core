// fpga/vitis-app/mipi_fw/src/i2c_bitbang.h
//
// Software bit-bang I2C over AXI GPIO (open-drain emulation via tri-state).
// SCL = GPIO bit 4, SDA = GPIO bit 5.
// Pull low: gpio_tri bit = 0, gpio_data bit = 0
// Release (high-Z, external pull-up): gpio_tri bit = 1
// Read SDA: release SDA, then read gpio_data_i bit 5.

#ifndef I2C_BITBANG_H
#define I2C_BITBANG_H

#include <stdint.h>

#define I2C_OK       0
#define I2C_NACK    -1
#define I2C_TIMEOUT -2

void i2c_init(void);

// Release bus and sample SCL/SDA pad levels (1=high). Returns 0 if both idle-high.
int i2c_bus_idle(uint8_t *scl, uint8_t *sda);

// Send write-address byte only; I2C_OK if slave ACKs.
int i2c_probe(uint8_t addr);

// Write `len` bytes from `data` to 7-bit slave `addr`.
// Returns I2C_OK on success, I2C_NACK if slave did not acknowledge.
int i2c_write(uint8_t addr, const uint8_t *data, uint16_t len);

// Write `wlen` bytes from `wdata`, then repeated-start read `rlen` bytes into `rdata`.
// Typical use: write register address, then read register value.
int i2c_write_read(uint8_t addr, const uint8_t *wdata, uint16_t wlen,
                   uint8_t *rdata, uint16_t rlen);

#endif
