// fpga/vitis/mipi_fw/src/log.h
#ifndef LOG_H
#define LOG_H

#include "xil_printf.h"

#define LOG_BOOT_TOTAL  14u

static inline void log_boot_header(void) {
    xil_printf("\r\n"
               "========================================\r\n"
               "  MIPI Validation Platform FW v1.0\r\n"
               "========================================\r\n");
}

static inline void log_step_begin(unsigned step, const char *label) {
    xil_printf("[BOOT %02u/%02u] %s ...\r\n",
               step, (unsigned)LOG_BOOT_TOTAL, label);
}

static inline void log_step_ok(void) {
    xil_printf("              -> OK\r\n");
}

static inline void log_step_fail_int(int rc) {
    xil_printf("              -> FAIL (rc=%d)\r\n", rc);
}

static inline void log_step_skip(const char *reason) {
    xil_printf("              -> SKIP (%s)\r\n", reason);
}

static inline void log_boot_done(void) {
    xil_printf("========================================\r\n"
               "  Boot complete. Main loop running.\r\n"
               "========================================\r\n\r\n");
}

#endif
