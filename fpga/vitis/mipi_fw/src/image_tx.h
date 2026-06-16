// fpga/vitis-app/mipi_fw/src/image_tx.h
#ifndef IMAGE_TX_H
#define IMAGE_TX_H

#include <stdint.h>

#define IMG_DATA_HEADER_0 0xBB
#define IMG_DATA_HEADER_1 0x66
#define IMG_EOT_HEADER_0  0xBB
#define IMG_EOT_HEADER_1  0x99
#define IMG_CHUNK_SIZE    512

int capture_and_send(uint16_t width, uint16_t height);

#endif
