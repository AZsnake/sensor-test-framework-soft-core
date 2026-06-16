// fpga/vitis/mipi_fw/src/sensor.c
#include "sensor.h"
#include "i2c_bitbang.h"
#include "hw_defs.h"
#include "imx298_init_regs.h"
#include "xgpio.h"
#include "sleep.h"
#include "xil_printf.h"

extern XGpio gpio_inst;

// Update only RESET/PWDN bits; leave SCL/SDA DATA/TRI to i2c_bitbang.
static void gpio_set_cam(uint32_t mask, uint32_t bits) {
    uint32_t v = XGpio_DiscreteRead(&gpio_inst, 1);
    v = (v & ~mask) | (bits & mask);
    XGpio_DiscreteWrite(&gpio_inst, 1, v);
}

void sensor_gpio_init(void) {
    // bit0/1 = output (RESET/PWDN), bit2/3 = input/high-Z (I2C)
    XGpio_SetDataDirection(&gpio_inst, 1, GPIO_I2C_SCL | GPIO_I2C_SDA);
    // 实测两根线均反相(经 MENTOR GPIO 板/TX0108, 见 spec §3.5.1):
    //   XCLR=0 出复位, PWDN=1 正常工作(PWDN 管脚悬空时 sensor 默认正常,接上后须驱 1)
    gpio_set_cam(GPIO_XCLR | GPIO_PWDN, GPIO_PWDN);  // XCLR=0 出复位, PWDN=1 正常
    usleep(10000);
}

static int sensor_write_reg(uint16_t reg, uint8_t val) {
    uint8_t buf[3] = { (uint8_t)(reg >> 8), (uint8_t)(reg & 0xFF), val };
    return i2c_write(IMX298_I2C_ADDR, buf, 3);
}

static int sensor_read_reg(uint16_t reg, uint8_t *val) {
    uint8_t addr[2] = { (uint8_t)(reg >> 8), (uint8_t)(reg & 0xFF) };
    return i2c_write_read(IMX298_I2C_ADDR, addr, 2, val, 1);
}

void sensor_reset(void) {
    // 实测两根线均反相 (spec §3.5.1): XCLR=1 进复位 → XCLR=0 出复位; PWDN=1 正常工作
    gpio_set_cam(GPIO_XCLR | GPIO_PWDN, GPIO_XCLR | GPIO_PWDN);  // 进复位 (XCLR=1), PWDN=1
    usleep(1000);
    gpio_set_cam(GPIO_XCLR, 0);                                  // 出复位 (XCLR=0), PWDN 保持 1
    usleep(20000);
    i2c_init();
}

static void sensor_i2c_diag(void) {
    uint8_t scl = 0, sda = 0;
    uint32_t gpio = XGpio_DiscreteRead(&gpio_inst, 1);

    (void)i2c_bus_idle(&scl, &sda);
    xil_printf("IMX298: bus SCL=%u SDA=%u XCLR=%u PWDN=%u\r\n",
               scl, sda,
               (gpio & GPIO_XCLR) ? 1U : 0U,
               (gpio & GPIO_PWDN) ? 1U : 0U);
    if (!scl || !sda)
        xil_printf("IMX298: I2C bus not idle-high (check pull-up/wiring)\r\n");
    if (i2c_probe(IMX298_I2C_ADDR) != I2C_OK)
        xil_printf("IMX298: no ACK at 0x%02X (power/EXTCLK/addr)\r\n",
                   IMX298_I2C_ADDR);

    // Quick scan: empty bus => wiring/power/INCK; only 0x5x => EEPROM, not sensor
    static const uint8_t scan[] = { 0x1A, 0x10, 0x36, 0x50, 0x51, 0x52, 0x53 };
    int acks = 0;
    for (unsigned i = 0; i < sizeof(scan); i++) {
        if (i2c_probe(scan[i]) == I2C_OK) {
            xil_printf("IMX298: I2C ACK at 0x%02X\r\n", scan[i]);
            acks++;
        }
    }
    if (acks == 0)
        xil_printf("IMX298: I2C scan: no devices (check module power/INCK/wiring)\r\n");
}

int sensor_init(void) {
    sensor_reset();
    sensor_i2c_diag();

    // Probe 0x0112 (RAW10 pixel format MSB, expect 0x0A after power-on)
    uint8_t id = 0;
    int probe = I2C_NACK;
    for (int attempt = 0; attempt < 3; attempt++) {
        probe = sensor_read_reg(0x0112, &id);
        if (probe == I2C_OK)
            break;
        usleep(10000);
    }
    if (probe != I2C_OK) {
        xil_printf("IMX298: I2C NACK on chip-id read (check addr/power/EXTCLK)\r\n");
        return -1;
    }
    xil_printf("IMX298: reg[0x0112]=0x%02x\r\n", id);

    // 写完整初始化表 (1076 条; 末尾 stream-on 不在表内)
    for (uint32_t i = 0; i < IMX298_INIT_REGS_COUNT; i++) {
        if (sensor_write_reg(IMX298_INIT_REGS[i].reg,
                             IMX298_INIT_REGS[i].val) != I2C_OK) {
            xil_printf("IMX298: write NACK @0x%04x (idx %u)\r\n",
                       IMX298_INIT_REGS[i].reg, (unsigned)i);
            return -2;
        }
    }
    xil_printf("IMX298: %u init regs OK\r\n", (unsigned)IMX298_INIT_REGS_COUNT);
    return 0;
}

void sensor_stream_on(void)  { sensor_write_reg(0x0100, 0x01); }
void sensor_stream_off(void) { sensor_write_reg(0x0100, 0x00); }
