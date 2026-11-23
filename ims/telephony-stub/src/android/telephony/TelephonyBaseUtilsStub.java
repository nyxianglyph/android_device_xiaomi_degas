/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package android.telephony;

/**
 * Stock mediatek-ims-common asks this HyperOS framework class whether it runs
 * on MIUI before it takes Xiaomi specific paths. It does not here.
 */
public final class TelephonyBaseUtilsStub {
    private TelephonyBaseUtilsStub() {}

    public static boolean isMiuiRom() {
        return false;
    }
}
