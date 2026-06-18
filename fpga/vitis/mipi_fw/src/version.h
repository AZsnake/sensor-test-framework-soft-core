// fpga/vitis/mipi_fw/src/version.h
#ifndef VERSION_H
#define VERSION_H

/* ========== 用户可编辑区：修改此处即可更新全固件版本信息 ========== */

#define FW_APP_NAME          "MIPI Validation Platform FW"

#define FW_VERSION_MAJOR     0
#define FW_VERSION_MINOR     0
#define FW_VERSION_PATCH     5

/* ========== 自动生成区：供打印输出及代码引用，一般无需修改 ========== */

#define VERSION_JOIN2_(maj, min)       #maj "." #min
#define VERSION_JOIN3_(maj, min, pat)  #maj "." #min "." #pat
#define VERSION_TAG_(maj, min)         "v" #maj "." #min
#define VERSION_TAG3_(maj, min, pat)   "v" #maj "." #min "." #pat

#define FW_VERSION_SHORT     VERSION_JOIN2_(FW_VERSION_MAJOR, FW_VERSION_MINOR)
#define FW_VERSION_STRING    VERSION_JOIN3_(FW_VERSION_MAJOR, FW_VERSION_MINOR, FW_VERSION_PATCH)
#define FW_VERSION_TAG       VERSION_TAG_(FW_VERSION_MAJOR, FW_VERSION_MINOR)
#define FW_VERSION_TAG_FULL  VERSION_TAG3_(FW_VERSION_MAJOR, FW_VERSION_MINOR, FW_VERSION_PATCH)

#endif
