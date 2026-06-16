// fpga/vitis/mipi_fw/src/sensor.h
// IMX298 上电初始化 / 流控 (2-lane RAW10, 寄存器表见 imx298_init_regs.h)
#ifndef SENSOR_H
#define SENSOR_H

void sensor_gpio_init(void);   // GPIO direction + PWDN/XCLR defaults
void sensor_reset(void);       // power-on + XCLR reset pulse
int  sensor_init(void);        // 复位 + 校验ID + 写初始化表; 0=OK, <0=失败
void sensor_stream_on(void);   // 0x0100 = 1
void sensor_stream_off(void);  // 0x0100 = 0

#endif
