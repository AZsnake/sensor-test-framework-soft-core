// fpga/rtl/axis_uram_framebuf.v
// URAM frame buffer: AXIS slave write (32-bit from AXIS Switch), AXI-Lite read.
// Address space (ADDR_WIDTH=25, 32 MB):
//   0x0000_0000 – 0x00FF_FFFF: frame data (read-only)
//   0x0100_0000 + offset: control registers
//     +0x00: ARM    [0]    RW  write 1 to arm capture; auto-clear on frame done
//     +0x04: DONE   [0]    RO  frame capture complete (cleared on ARM write)
//     +0x08: BYTES  [31:0] RO  captured byte count
//     +0x0C: STATUS [1:0]  RO  bit0=capturing, bit1=overflow
`timescale 1ns/1ps

module axis_uram_framebuf #(
    parameter integer FRAMEBUF_BYTES     = 16777216,  // 16 MiB default
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 32
)(
    // AXI-Lite read / control (MicroBlaze clock domain)
    input  wire                                s_axi_aclk,
    input  wire                                s_axi_aresetn,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]       s_axi_awaddr,
    input  wire                                s_axi_awvalid,
    output wire                                s_axi_awready,
    input  wire [C_S_AXI_DATA_WIDTH-1:0]       s_axi_wdata,
    input  wire [C_S_AXI_DATA_WIDTH/8-1:0]     s_axi_wstrb,
    input  wire                                s_axi_wvalid,
    output wire                                s_axi_wready,
    output wire [1:0]                          s_axi_bresp,
    output wire                                s_axi_bvalid,
    input  wire                                s_axi_bready,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0]       s_axi_araddr,
    input  wire                                s_axi_arvalid,
    output wire                                s_axi_arready,
    output wire [C_S_AXI_DATA_WIDTH-1:0]       s_axi_rdata,
    output wire [1:0]                          s_axi_rresp,
    output wire                                s_axi_rvalid,
    input  wire                                s_axi_rready,

    // AXI4-Stream write (AXIS Switch clock domain)
    input  wire                                s_axis_aclk,
    input  wire                                s_axis_aresetn,
    input  wire [31:0]                         s_axis_tdata,
    input  wire                                s_axis_tvalid,
    output wire                                s_axis_tready,
    input  wire                                s_axis_tlast,
    input  wire [0:0]                          s_axis_tuser,

    output wire                                frame_done
);

    localparam integer MEM_DEPTH = FRAMEBUF_BYTES / 8;
    localparam integer MEM_ADDR_W = (MEM_DEPTH <= 1) ? 1 : $clog2(MEM_DEPTH);
    localparam [24:0] CTRL_BASE = 25'h1000000;

    // Both RAM ports run on s_axis_aclk with synchronous read: URAM inference
    // requires a single clock and a registered read (UG901). AXI-Lite reads
    // cross into the AXIS domain via a toggle handshake below.
    (* ram_style = "ultra" *)
    reg [63:0] mem [0:MEM_DEPTH-1];

    // Cross-domain signals, declared up front (driven in sections below)
    reg         done_axis;
    reg  [31:0] bytes_axis;
    reg  [1:0]  status_axis;
    reg         done_sync1, done_sync2, done_sync2_d;
    wire        done_pulse_axi;
    reg  [31:0] bytes_sync1, bytes_sync2;
    reg  [1:0]  status_sync1, status_sync2;
    wire [31:0] bytes_sync;
    wire [1:0]  status_sync;
    reg         rd_ack_tog;
    reg  [63:0] rd_data_axis;

    // -------------------------------------------------------------------------
    // AXI-Lite write path (ARM register only)
    // -------------------------------------------------------------------------
    reg aw_ready, w_ready;
    reg [1:0] b_resp;
    reg b_valid;
    reg [C_S_AXI_ADDR_WIDTH-1:0] aw_addr_latched;

    reg arm_axi;
    reg done_axi;
    reg [31:0] bytes_axi;
    reg [1:0] status_axi;

    assign s_axi_awready = aw_ready;
    assign s_axi_wready  = w_ready;
    assign s_axi_bresp   = b_resp;
    assign s_axi_bvalid  = b_valid;

    wire [24:0] aw_addr25 = aw_addr_latched[24:0];
    wire [24:0] ar_addr25 = s_axi_araddr[24:0];
    wire ctrl_write = (aw_addr25 >= CTRL_BASE);

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn)
            aw_ready <= 1'b0;
        else if (!aw_ready && s_axi_awvalid && s_axi_wvalid)
            aw_ready <= 1'b1;
        else
            aw_ready <= 1'b0;
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn)
            aw_addr_latched <= 0;
        else if (!aw_ready && s_axi_awvalid && s_axi_wvalid)
            aw_addr_latched <= s_axi_awaddr;
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn)
            w_ready <= 1'b0;
        else if (!w_ready && s_axi_awvalid && s_axi_wvalid)
            w_ready <= 1'b1;
        else
            w_ready <= 1'b0;
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            arm_axi  <= 1'b0;
            done_axi <= 1'b0;
        end else if (aw_ready && s_axi_awvalid && w_ready && s_axi_wvalid) begin
            if (ctrl_write && aw_addr25[6:2] == 5'h0 && s_axi_wdata[0]) begin
                arm_axi  <= 1'b1;
                done_axi <= 1'b0;
            end
        end else if (done_pulse_axi) begin
            arm_axi  <= 1'b0;
            done_axi <= 1'b1;
        end
    end

    always @(posedge s_axi_aclk) begin
        if (done_pulse_axi)
            bytes_axi <= bytes_sync;
        if (done_pulse_axi)
            status_axi <= status_sync;
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            b_valid <= 1'b0;
            b_resp  <= 2'b00;
        end else if (aw_ready && s_axi_awvalid && w_ready && s_axi_wvalid && !b_valid) begin
            b_valid <= 1'b1;
            b_resp  <= (ctrl_write && aw_addr25[6:2] == 5'h0) ? 2'b00 : 2'b10;
        end else if (s_axi_bready && b_valid)
            b_valid <= 1'b0;
    end

    // -------------------------------------------------------------------------
    // AXI-Lite read path
    // -------------------------------------------------------------------------
    reg ar_ready;
    reg [C_S_AXI_DATA_WIDTH-1:0] r_data;
    reg [1:0] r_resp;
    reg r_valid;

    assign s_axi_arready = ar_ready;
    assign s_axi_rdata   = r_data;
    assign s_axi_rresp   = r_resp;
    assign s_axi_rvalid  = r_valid;

    wire data_read = (ar_addr25 < CTRL_BASE);

    // Frame-data reads cross to the AXIS clock domain via toggle handshake:
    // latch the address, flip rd_req_tog, wait for rd_ack_tog to flip back.
    reg        rd_pending;
    reg        rd_req_tog;
    reg [24:0] rd_addr_axi;

    reg ack_sync1, ack_sync2, ack_sync2_d;
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            ack_sync1   <= 1'b0;
            ack_sync2   <= 1'b0;
            ack_sync2_d <= 1'b0;
        end else begin
            ack_sync1   <= rd_ack_tog;
            ack_sync2   <= ack_sync1;
            ack_sync2_d <= ack_sync2;
        end
    end
    wire rd_ack_pulse = ack_sync2 ^ ack_sync2_d;

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn)
            ar_ready <= 1'b0;
        else if (!ar_ready && s_axi_arvalid && !rd_pending && !r_valid)
            ar_ready <= 1'b1;
        else
            ar_ready <= 1'b0;
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            r_valid     <= 1'b0;
            r_resp      <= 2'b00;
            r_data      <= 32'd0;
            rd_pending  <= 1'b0;
            rd_req_tog  <= 1'b0;
            rd_addr_axi <= 25'd0;
        end else if (ar_ready && s_axi_arvalid && !r_valid && !rd_pending) begin
            if (data_read) begin
                rd_addr_axi <= ar_addr25;
                rd_req_tog  <= ~rd_req_tog;
                rd_pending  <= 1'b1;
            end else begin
                r_valid <= 1'b1;
                case (ar_addr25[6:2])
                    5'h0: r_data <= {31'b0, arm_axi};
                    5'h1: r_data <= {31'b0, done_axi};
                    5'h2: r_data <= bytes_axi;
                    5'h3: r_data <= {30'b0, status_axi};
                    default: begin
                        r_data <= 32'hDEAD_BEEF;
                        r_resp <= 2'b10;
                    end
                endcase
                if (ar_addr25[6:2] != 5'h4)
                    r_resp <= 2'b00;
            end
        end else if (rd_pending && rd_ack_pulse) begin
            rd_pending <= 1'b0;
            r_valid    <= 1'b1;
            r_resp     <= 2'b00;
            // rd_data_axis is stable: written before rd_ack_tog flipped and
            // held until the next request.
            r_data     <= rd_addr_axi[2] ? rd_data_axis[63:32]
                                         : rd_data_axis[31:0];
        end else if (r_valid && s_axi_rready)
            r_valid <= 1'b0;
    end

    // -------------------------------------------------------------------------
    // RAM read port (s_axis_aclk domain, synchronous read for URAM)
    // -------------------------------------------------------------------------
    reg req_sync1, req_sync2, req_sync2_d;
    reg [MEM_ADDR_W-1:0] rd_idx_axis;
    reg rd_ram_stage;

    always @(posedge s_axis_aclk) begin
        if (!s_axis_aresetn) begin
            req_sync1    <= 1'b0;
            req_sync2    <= 1'b0;
            req_sync2_d  <= 1'b0;
            rd_ack_tog   <= 1'b0;
            rd_ram_stage <= 1'b0;
        end else begin
            req_sync1   <= rd_req_tog;
            req_sync2   <= req_sync1;
            req_sync2_d <= req_sync2;
            rd_ram_stage <= 1'b0;
            if (req_sync2 ^ req_sync2_d) begin
                // rd_addr_axi is stable while the handshake is in flight
                rd_idx_axis  <= rd_addr_axi[MEM_ADDR_W+2:3];
                rd_ram_stage <= 1'b1;
            end else if (rd_ram_stage) begin
                rd_ack_tog <= ~rd_ack_tog;
            end
        end
    end

    always @(posedge s_axis_aclk) begin
        if (rd_ram_stage)
            rd_data_axis <= mem[rd_idx_axis];
    end

    // -------------------------------------------------------------------------
    // Cross-domain: ARM (AXI -> AXIS), DONE/BYTES/STATUS (AXIS -> AXI)
    // -------------------------------------------------------------------------
    reg arm_sync1, arm_sync2;
    always @(posedge s_axis_aclk) begin
        if (!s_axis_aresetn) begin
            arm_sync1 <= 1'b0;
            arm_sync2 <= 1'b0;
        end else begin
            arm_sync1 <= arm_axi;
            arm_sync2 <= arm_sync1;
        end
    end

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            done_sync1  <= 1'b0;
            done_sync2  <= 1'b0;
            done_sync2_d <= 1'b0;
        end else begin
            done_sync1   <= done_axis;
            done_sync2   <= done_sync1;
            done_sync2_d <= done_sync2;
        end
    end
    assign done_pulse_axi = done_sync2 && !done_sync2_d;

    always @(posedge s_axi_aclk) begin
        bytes_sync1  <= bytes_axis;
        bytes_sync2  <= bytes_sync1;
        status_sync1 <= status_axis;
        status_sync2 <= status_sync1;
    end
    assign bytes_sync  = bytes_sync2;
    assign status_sync = status_sync2;

    // -------------------------------------------------------------------------
    // AXIS capture FSM
    // -------------------------------------------------------------------------
    localparam [1:0] CAP_WAIT_SOF = 2'd0;
    localparam [1:0] CAP_WRITE    = 2'd1;

    reg [1:0] cap_state;
    reg capturing;
    reg overflow_axis;
    reg wr_odd;
    reg [31:0] wr_lo;
    reg [MEM_ADDR_W-1:0] wr_ptr;
    reg [31:0] byte_count;
    reg done_axis_d;
    reg frame_finish;

    assign s_axis_tready = 1'b1;
    assign frame_done    = done_axis && !done_axis_d;

    wire beat = s_axis_tvalid;
    wire sof  = s_axis_tvalid && s_axis_tuser[0];
    wire would_overflow = (byte_count + 32'd4) > FRAMEBUF_BYTES;

    always @(posedge s_axis_aclk) begin
        done_axis_d <= done_axis;
        frame_finish <= 1'b0;

        if (!s_axis_aresetn) begin
            cap_state     <= CAP_WAIT_SOF;
            capturing     <= 1'b0;
            overflow_axis <= 1'b0;
            wr_odd        <= 1'b0;
            wr_lo         <= 32'd0;
            wr_ptr        <= {MEM_ADDR_W{1'b0}};
            byte_count    <= 32'd0;
            done_axis     <= 1'b0;
            bytes_axis    <= 32'd0;
            status_axis   <= 2'd0;
        end else begin
            done_axis <= 1'b0;

            if (frame_finish) begin
                if (wr_odd && !overflow_axis)
                    mem[wr_ptr] <= {32'd0, wr_lo};
                bytes_axis    <= byte_count;
                status_axis   <= {overflow_axis, 1'b0};
                done_axis     <= 1'b1;
                cap_state     <= CAP_WAIT_SOF;
                capturing     <= 1'b0;
                wr_odd        <= 1'b0;
            end else if (!arm_sync2) begin
                cap_state     <= CAP_WAIT_SOF;
                capturing     <= 1'b0;
                overflow_axis <= 1'b0;
            end else if (cap_state == CAP_WAIT_SOF) begin
                capturing <= 1'b0;
                if (sof) begin
                    cap_state     <= CAP_WRITE;
                    capturing     <= 1'b1;
                    overflow_axis <= 1'b0;
                    wr_odd        <= 1'b0;
                    wr_ptr        <= {MEM_ADDR_W{1'b0}};
                    byte_count    <= 32'd4;
                    wr_lo         <= s_axis_tdata;
                    wr_odd        <= 1'b1;
                    if (32'd4 > FRAMEBUF_BYTES)
                        overflow_axis <= 1'b1;
                end
            end else begin
                capturing <= 1'b1;
                if (sof) begin
                    frame_finish <= 1'b1;
                end else if (beat) begin
                    if (would_overflow || overflow_axis) begin
                        overflow_axis <= 1'b1;
                        frame_finish  <= 1'b1;
                    end else begin
                        byte_count <= byte_count + 32'd4;
                        if (!wr_odd) begin
                            wr_lo  <= s_axis_tdata;
                            wr_odd <= 1'b1;
                        end else begin
                            mem[wr_ptr] <= {s_axis_tdata, wr_lo};
                            wr_ptr      <= wr_ptr + 1'b1;
                            wr_odd      <= 1'b0;
                        end
                    end
                end
            end
        end
    end

endmodule
