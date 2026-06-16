// fpga/vitis-app/mipi_fw/src/protocol.h
#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

#define FRAME_HEADER_0  0xAA
#define FRAME_HEADER_1  0x55
#define MAX_PAYLOAD_LEN 256

// Command codes
#define CMD_WRITE_REG    0x01
#define CMD_READ_REG     0x02
#define CMD_READ_STATUS  0x03
#define CMD_CAPTURE      0x04
#define CMD_GPIO_CTRL    0x05
#define CMD_RESET_SEQ    0x06
#define CMD_SET_SOURCE   0x07
#define CMD_SET_PORT     0x08
#define CMD_CLR_ERR      0x0A

#define CMD_ACK          0x80
#define CMD_ERR          0x81

// Error codes
#define ERR_I2C_NACK       0x01
#define ERR_I2C_TIMEOUT    0x02
#define ERR_INVALID_CMD    0x03
#define ERR_INVALID_PARAM  0x04
#define ERR_VDMA_FAIL      0x05
#define ERR_MIPI_NOT_READY 0x06
#define ERR_CHECKSUM       0x07
#define ERR_BUSY           0x08

typedef struct {
    uint8_t cmd;
    uint16_t len;
    uint8_t payload[MAX_PAYLOAD_LEN];
    uint8_t checksum;
} frame_t;

// Parse state machine states
typedef enum {
    PARSE_IDLE,
    PARSE_HEADER1,
    PARSE_CMD,
    PARSE_LEN_H,
    PARSE_LEN_L,
    PARSE_PAYLOAD,
    PARSE_CHECKSUM
} parse_state_t;

typedef struct {
    parse_state_t state;
    frame_t       frame;
    uint16_t      payload_idx;
    uint8_t       calc_checksum;
} parser_t;

void parser_init(parser_t *p);
int  parser_feed(parser_t *p, uint8_t byte);  // returns 1 when frame complete

uint8_t calc_checksum(uint8_t cmd, uint16_t len, const uint8_t *payload);
void send_ack(uint8_t orig_cmd);
void send_err(uint8_t error_code);
void send_response(uint8_t cmd, const uint8_t *payload, uint16_t len);

#endif
