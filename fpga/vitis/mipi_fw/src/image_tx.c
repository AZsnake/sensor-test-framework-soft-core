// fpga/vitis-app/mipi_fw/src/image_tx.c
#include "image_tx.h"
#include "hw_defs.h"
#include "protocol.h"
#include "xuartlite.h"
#include "xil_io.h"
#include "sleep.h"

extern XUartLite uart_inst;

static void uart_send_raw(const uint8_t *data, uint32_t len) {
    for (uint32_t i = 0; i < len; i++) {
        while (XUartLite_IsSending(&uart_inst)) {}
        XUartLite_Send(&uart_inst, (u8 *)&data[i], 1);
    }
}

static void send_image_chunk(uint16_t seq, uint32_t fb_off, uint16_t chunk_len) {
    uint8_t hdr[6] = {
        IMG_DATA_HEADER_0, IMG_DATA_HEADER_1,
        (uint8_t)(seq >> 8), (uint8_t)(seq & 0xFF),
        (uint8_t)(chunk_len >> 8), (uint8_t)(chunk_len & 0xFF)
    };
    uart_send_raw(hdr, 6);

    uint8_t cs = hdr[2] ^ hdr[3] ^ hdr[4] ^ hdr[5];
    for (uint16_t i = 0; i < chunk_len; i += 4) {
        uint32_t word = Xil_In32(FRAMEBUF_BASEADDR + fb_off + i);
        for (int b = 0; b < 4 && (i + b) < chunk_len; b++) {
            uint8_t byte = (uint8_t)(word >> (8 * b));
            uart_send_raw(&byte, 1);
            cs ^= byte;
        }
    }
    uart_send_raw(&cs, 1);
}

static void send_eot(uint32_t total_bytes) {
    uint8_t eot[6] = {
        IMG_EOT_HEADER_0, IMG_EOT_HEADER_1,
        (uint8_t)(total_bytes >> 24), (uint8_t)(total_bytes >> 16),
        (uint8_t)(total_bytes >> 8),  (uint8_t)(total_bytes & 0xFF)
    };
    uart_send_raw(eot, 6);
}

int capture_and_send(uint16_t width, uint16_t height) {
    uint32_t stride = (uint32_t)width * 10 / 8;
    uint32_t frame_size = stride * height;

    Xil_Out32(FB_REG_ARM, 1);

    int timeout_ms = 5000;
    while (timeout_ms > 0) {
        if (Xil_In32(FB_REG_DONE) & 1)
            break;
        usleep(1000);
        timeout_ms--;
    }
    if (timeout_ms <= 0) return -1;

    uint32_t captured = Xil_In32(FB_REG_BYTES);
    if (captured < frame_size)
        frame_size = captured;

    uint16_t seq = 0;
    uint32_t sent = 0;
    while (sent < frame_size) {
        uint16_t chunk = (frame_size - sent > IMG_CHUNK_SIZE)
                         ? IMG_CHUNK_SIZE : (uint16_t)(frame_size - sent);
        send_image_chunk(seq++, sent, chunk);
        sent += chunk;
    }
    send_eot(sent);

    return 0;
}
