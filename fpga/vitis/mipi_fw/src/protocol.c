// fpga/vitis-app/mipi_fw/src/protocol.c
#include "protocol.h"
#include "xuartlite.h"
#include "hw_defs.h"

extern XUartLite uart_inst;

void parser_init(parser_t *p) {
    p->state = PARSE_IDLE;
    p->payload_idx = 0;
    p->calc_checksum = 0;
}

int parser_feed(parser_t *p, uint8_t byte) {
    switch (p->state) {
    case PARSE_IDLE:
        if (byte == FRAME_HEADER_0) p->state = PARSE_HEADER1;
        break;
    case PARSE_HEADER1:
        p->state = (byte == FRAME_HEADER_1) ? PARSE_CMD : PARSE_IDLE;
        break;
    case PARSE_CMD:
        p->frame.cmd = byte;
        p->calc_checksum = byte;
        p->state = PARSE_LEN_H;
        break;
    case PARSE_LEN_H:
        p->frame.len = (uint16_t)byte << 8;
        p->calc_checksum ^= byte;
        p->state = PARSE_LEN_L;
        break;
    case PARSE_LEN_L:
        p->frame.len |= byte;
        p->calc_checksum ^= byte;
        p->payload_idx = 0;
        if (p->frame.len > MAX_PAYLOAD_LEN) {
            p->state = PARSE_IDLE;
        } else if (p->frame.len == 0) {
            p->state = PARSE_CHECKSUM;
        } else {
            p->state = PARSE_PAYLOAD;
        }
        break;
    case PARSE_PAYLOAD:
        p->frame.payload[p->payload_idx++] = byte;
        p->calc_checksum ^= byte;
        if (p->payload_idx >= p->frame.len)
            p->state = PARSE_CHECKSUM;
        break;
    case PARSE_CHECKSUM:
        p->frame.checksum = byte;
        p->state = PARSE_IDLE;
        return (byte == p->calc_checksum) ? 1 : -1;
    }
    return 0;
}

uint8_t calc_checksum(uint8_t cmd, uint16_t len, const uint8_t *payload) {
    uint8_t cs = cmd ^ (uint8_t)(len >> 8) ^ (uint8_t)(len & 0xFF);
    for (uint16_t i = 0; i < len; i++)
        cs ^= payload[i];
    return cs;
}

static void uart_send_bytes(const uint8_t *data, uint16_t len) {
    for (uint16_t i = 0; i < len; i++) {
        while (XUartLite_IsSending(&uart_inst)) {}
        XUartLite_Send(&uart_inst, (u8 *)&data[i], 1);
    }
}

void send_response(uint8_t cmd, const uint8_t *payload, uint16_t len) {
    uint8_t hdr[5] = {FRAME_HEADER_0, FRAME_HEADER_1, cmd,
                      (uint8_t)(len >> 8), (uint8_t)(len & 0xFF)};
    uart_send_bytes(hdr, 5);
    if (len > 0) uart_send_bytes(payload, len);
    uint8_t cs = calc_checksum(cmd, len, payload);
    uart_send_bytes(&cs, 1);
}

void send_ack(uint8_t orig_cmd) {
    send_response(CMD_ACK, &orig_cmd, 1);
}

void send_err(uint8_t error_code) {
    send_response(CMD_ERR, &error_code, 1);
}
