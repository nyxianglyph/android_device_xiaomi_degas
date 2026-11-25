/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.database.ContentObserver;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemProperties;
import android.os.UserHandle;
import android.provider.Settings;
import android.util.Log;

/**
 * Makes the color mode of the display settings reach the panel.
 *
 * The color modes of this phone are render intents of the stock composer, and
 * the system selects them there by itself. That is only half of a mode: the
 * stock display feature service applies the other half (the white point and
 * the contrast of the scheme) and has to be told which scheme is in use. With
 * nobody telling it, the colors are neither one scheme nor another.
 */
final class ColorScheme {
    private static final String TAG = "DegasColorScheme";

    private static final String SERVICE =
            "vendor.xiaomi.hardware.displayfeature_aidl.IDisplayFeature/default";
    private static final String DESCRIPTOR =
            "vendor.xiaomi.hardware.displayfeature_aidl.IDisplayFeature";
    // void setFeature(int displayId, int mode, int value, int cookie)
    private static final int TRANSACTION_SET_FEATURE = IBinder.FIRST_CALL_TRANSACTION + 6;
    private static final int DISPLAY_PRIMARY = 0;
    private static final int VALUE_ON = 2;
    private static final int COOKIE = 255;

    // The color modes (config_availableColorModes) and the scheme of the
    // display feature service that belongs to each.
    private static final int[][] SCHEMES = {
            {258, 0},  // vivid: "automatic contrast"
            {256, 1},  // saturated: "increased contrast"
            {257, 2},  // original color: "standard"
    };

    // What the system falls back to while no mode has been chosen.
    private static final String PROPERTY_COLOR_MODE = "persist.sys.sf.native_mode";

    private static final int RETRY_MS = 2000;
    private static final int RETRIES = 10;

    private final Context mContext;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final Runnable mRetry = this::apply;
    private int mRetriesLeft = RETRIES;

    ColorScheme(Context context) {
        mContext = context;
        context.getContentResolver().registerContentObserver(
                Settings.System.getUriFor(Settings.System.DISPLAY_COLOR_MODE), false,
                new ContentObserver(mHandler) {
                    @Override
                    public void onChange(boolean selfChange) {
                        apply();
                    }
                }, UserHandle.USER_ALL);
        context.registerReceiverAsUser(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                apply();
            }
        }, UserHandle.ALL, new IntentFilter(Intent.ACTION_USER_SWITCHED), null, mHandler);
        apply();
    }

    private void apply() {
        mHandler.removeCallbacks(mRetry);
        int colorMode = Settings.System.getIntForUser(mContext.getContentResolver(),
                Settings.System.DISPLAY_COLOR_MODE,
                SystemProperties.getInt(PROPERTY_COLOR_MODE, -1), UserHandle.USER_CURRENT);
        for (int[] scheme : SCHEMES) {
            if (scheme[0] != colorMode) continue;
            if (VendorService.call(TAG, SERVICE, DESCRIPTOR, TRANSACTION_SET_FEATURE,
                    DISPLAY_PRIMARY, scheme[1], VALUE_ON, COOKIE)) {
                mRetriesLeft = RETRIES;
            } else if (mRetriesLeft-- > 0) {
                // This process can be up before the service is.
                mHandler.postDelayed(mRetry, RETRY_MS);
            }
            return;
        }
        Log.w(TAG, "no scheme for color mode " + colorMode);
    }
}
