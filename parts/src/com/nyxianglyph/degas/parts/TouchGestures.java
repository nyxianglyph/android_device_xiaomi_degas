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
import android.os.UserHandle;
import android.provider.Settings;

/**
 * Tells the touch controller what to watch for while the screen is off or
 * dozing. The controller finds the gestures by itself and its driver reports
 * them as keys; all it needs is to be told which ones are wanted, through the
 * stock touch feature service. The stock system does that, the power HAL of
 * this phone does not.
 *
 * <ul>
 * <li>Double tap follows the "Tap to wake" setting; the driver reports it as
 * KEY_WAKEUP.
 * <li>A finger on the fingerprint sensor is only reported from a dark or
 * dozing panel when the fingerprint mode is on. It is turned on when the
 * screen goes off and off again when the screen is on, where the fingerprint
 * overlay sees the finger as an ordinary touch. sensors/ hands the report to
 * the system.
 * </ul>
 */
final class TouchGestures {
    private static final String TAG = "DegasTouchGestures";

    private static final String SERVICE = "vendor.xiaomi.hw.touchfeature.ITouchFeature/default";
    private static final String DESCRIPTOR = "vendor.xiaomi.hw.touchfeature.ITouchFeature";
    // boolean setModeValue(int touchId, int mode, int value)
    private static final int TRANSACTION_SET_MODE_VALUE = IBinder.FIRST_CALL_TRANSACTION + 8;
    private static final int TOUCH_ID_PRIMARY = 0;
    private static final int MODE_FINGERPRINT = 10;
    private static final int MODE_DOUBLE_TAP = 14;

    private final Context mContext;
    private final Handler mHandler = new Handler(Looper.getMainLooper());

    TouchGestures(Context context) {
        mContext = context;
        context.getContentResolver().registerContentObserver(
                Settings.Secure.getUriFor(Settings.Secure.DOUBLE_TAP_TO_WAKE), false,
                new ContentObserver(mHandler) {
                    @Override
                    public void onChange(boolean selfChange) {
                        applyDoubleTap();
                    }
                }, UserHandle.USER_ALL);
        IntentFilter filter = new IntentFilter(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_SCREEN_ON);
        filter.addAction(Intent.ACTION_USER_SWITCHED);
        context.registerReceiverAsUser(new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                switch (intent.getAction()) {
                    case Intent.ACTION_SCREEN_OFF:
                        applyDoubleTap();
                        setMode(MODE_FINGERPRINT, 1);
                        break;
                    case Intent.ACTION_SCREEN_ON:
                        setMode(MODE_FINGERPRINT, 0);
                        break;
                    default:
                        applyDoubleTap();
                        break;
                }
            }
        }, UserHandle.ALL, filter, null, mHandler);
        applyDoubleTap();
    }

    private void applyDoubleTap() {
        boolean enabled = Settings.Secure.getIntForUser(mContext.getContentResolver(),
                Settings.Secure.DOUBLE_TAP_TO_WAKE, 0, UserHandle.USER_CURRENT) != 0;
        setMode(MODE_DOUBLE_TAP, enabled ? 1 : 0);
    }

    private static void setMode(int mode, int value) {
        VendorService.call(TAG, SERVICE, DESCRIPTOR, TRANSACTION_SET_MODE_VALUE,
                TOUCH_ID_PRIMARY, mode, value);
    }
}
