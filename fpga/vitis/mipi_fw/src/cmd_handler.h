// fpga/vitis-app/mipi_fw/src/cmd_handler.h
#ifndef CMD_HANDLER_H
#define CMD_HANDLER_H

#include "protocol.h"

void cmd_handler_init(void);
void cmd_dispatch(const frame_t *frame);

#endif
