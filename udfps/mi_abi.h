/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <linux/ioctl.h>
#include <linux/types.h>

/*
 * The few requests of Xiaomi's display driver the UDFPS handler uses. The
 * numbers and layouts are the user ABI of that driver (mi_disp in Xiaomi's
 * kernel sources); nothing else of its header is needed here.
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

struct mi_disp_brightness_req {
    struct mi_disp_base base;
    __u32 brightness; /* backlight level of the panel */
};

#define MI_DISP_IOCTL_GET_BRIGHTNESS _IOR('D', 0x0B, struct mi_disp_brightness_req)
#define MI_DISP_IOCTL_SET_LOCAL_HBM _IOW('D', 0x0E, struct mi_disp_local_hbm_req)

#define MI_DISP_LHBM_OFF_FINGER_UP 0
#define MI_DISP_LHBM_WHITE_1000NIT 2
#define MI_DISP_LHBM_WHITE_110NIT 3
