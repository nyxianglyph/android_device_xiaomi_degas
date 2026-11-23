/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <linux/ioctl.h>
#include <linux/types.h>

/*
 * The few requests of two Xiaomi kernel drivers the UDFPS handler uses. The
 * numbers and layouts are the user ABI of those drivers (mi_disp and
 * xiaomi_touch in Xiaomi's kernel sources); nothing else of their headers is
 * needed here.
 */

/* /dev/mi_display/disp_feature */
struct mi_disp_base {
    __u32 flag;
    __u32 disp_id; /* 0: primary display */
};

struct mi_disp_local_hbm_req {
    struct mi_disp_base base;
    __u32 local_hbm_value;
};

#define MI_DISP_IOCTL_SET_LOCAL_HBM _IOW('D', 0x0E, struct mi_disp_local_hbm_req)

#define MI_DISP_LHBM_OFF_FINGER_UP 0
#define MI_DISP_LHBM_WHITE_1000NIT 2

/* /dev/xiaomi-touch: the argument is int[XIAOMI_TOUCH_BUF_SIZE] = {touch id, mode, value}. */
#define XIAOMI_TOUCH_IOC_SET_CUR_VALUE _IO('T', 0)
#define XIAOMI_TOUCH_BUF_SIZE 256
#define XIAOMI_TOUCH_MODE_FOD_ENABLE 10
