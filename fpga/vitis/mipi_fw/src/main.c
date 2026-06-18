// fpga/vitis/mipi_fw/src/main.c
#include "xil_io.h"
#include "xstatus.h"
#include "xuartlite.h"
#include "xgpio.h"
#include "hw_defs.h"
#include "protocol.h"
#include "cmd_handler.h"
#include "i2c_bitbang.h"
#include "sensor.h"
#include "log.h"
#include "xpseudo_asm.h"   // csrr(): 读 RISC-V CSR
#include <stdint.h>

// 读 RISC-V cycle 计数器 (低32位)。此核 C_USE_COUNTERS=1, cycle 按 100MHz CPU 时钟
// 硬计数、自由运行 (CPU 在跑就在涨)。不用 rdtime/time CSR —— 本核未使能机器定时器
// 后端(C_USE_SLEEP=0), time CSR 不可靠, 主循环里会停摆导致心跳冻结。
#define read_cycle()    csrr(cycle)

// LED 心跳步进周期: 100 ms/步 @100MHz。cycle 低32位约 42.9s 回绕; 周期(10M) << 2^32,
// 无符号差值天然抗回绕。
#define LED_STEP_TICKS  (XPAR_CPU_CORE_CLOCK_FREQ_HZ / 10U)

XUartLite uart_inst;
XGpio gpio_inst;

static parser_t parser;

// UART 走主循环轮询 (非中断)
static void uart_poll(void) {
    uint8_t byte;
    while (XUartLite_Recv(&uart_inst, &byte, 1) == 1) {
        int result = parser_feed(&parser, byte);
        if (result == 1) {
            cmd_dispatch(&parser.frame);
        } else if (result == -1) {
            send_err(ERR_CHECKSUM);
        }
    }
}

int main(void) {
    int st;

    log_boot_header();

    log_step_begin(1, "UART Lite init");
    st = XUartLite_Initialize(&uart_inst, XPAR_AXI_UARTLITE_0_BASEADDR);
    if (st != XST_SUCCESS) {
        log_step_fail_int(st);
    } else {
        log_step_ok();
    }

    log_step_begin(2, "GPIO init");
    st = XGpio_Initialize(&gpio_inst, XPAR_AXI_GPIO_0_BASEADDR);
    if (st != XST_SUCCESS) {
        log_step_fail_int(st);
    } else {
        log_step_ok();
    }

    log_step_begin(3, "Sensor GPIO init");
    sensor_gpio_init();
    log_step_ok();

    log_step_begin(4, "I2C bitbang init");
    i2c_init();
    log_step_ok();

    parser_init(&parser);

    log_step_begin(5, "Command handler init");
    cmd_handler_init();   // 使能 CSI-2 RX core (要在 sensor 出流前就绪)
    log_step_ok();

    // 相机上电自动初始化 (2-lane RAW10): 复位 -> 校验ID -> 写寄存器表 -> 开流。
    log_step_begin(6, "IMX298 sensor init");
    if (sensor_init() == 0) {
        log_step_ok();

        log_step_begin(7, "IMX298 stream on");
        sensor_stream_on();
        log_step_ok();
    } else {
        log_step_fail_int(-1);

        log_step_begin(7, "IMX298 stream on");
        log_step_skip("sensor init failed");
    }

    // 清掉启动期间(sensor_init 打印窗口)回灌进 RX FIFO 的字节, 再进轮询主循环
    { uint8_t d; while (XUartLite_Recv(&uart_inst, &d, 1) == 1) { } }

    log_boot_done();

    // 主循环: 轮询 UART 命令 + LED 跑马灯心跳 (spec T1)。
    // 抓图(0x04)期间命令同步阻塞、心跳暂停, 属预期行为。
    uint8_t led = 0x01;
    u32 last_tick = read_cycle();
    while (1) {
        uart_poll();                       // 轮询 UART RX: 解析帧并派发命令
        u32 now = read_cycle();
        // 无符号差值抗回绕; 用 last=now (而非 +=步进) 使长阻塞命令后从当前时刻重新计相位,
        // 不会因积压的多个周期产生“追赶式”连闪。
        if ((u32)(now - last_tick) >= LED_STEP_TICKS) {
            last_tick = now;
            Xil_Out32(LED_GPIO_BASEADDR, led);
            led = (uint8_t)((led << 1) | (led >> 7));   // 循环左移
        }
    }

    return 0;
}
