/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.hardware.display.DisplayManager;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.Display;

/**
 * Lights the always-on display.
 *
 * In its low power mode the panel does not follow the backlight; it has two
 * brightness levels of its own, and it keeps the one it was given when the
 * display goes on to STATE_DOZE_SUSPEND. It only takes the request while the
 * display is in STATE_DOZE. Asked for nothing, it shows nothing, which is the
 * always-on display turning black a few seconds after the screen is locked.
 *
 * The stock system asks through the display feature service, and so does this:
 * the bright level or the dim one, by what the ambient light sensor for the
 * always-on display says, every time the display enters STATE_DOZE, and
 * "normal" again when the display is on.
 */
final class AodBrightness implements DisplayManager.DisplayListener, SensorEventListener {
    private static final String TAG = "DegasAodBrightness";

    private static final String SERVICE =
            "vendor.xiaomi.hardware.displayfeature_aidl.IDisplayFeature/default";
    private static final String DESCRIPTOR =
            "vendor.xiaomi.hardware.displayfeature_aidl.IDisplayFeature";
    // void setFeature(int displayId, int mode, int value, int cookie)
    private static final int TRANSACTION_SET_FEATURE = IBinder.FIRST_CALL_TRANSACTION + 6;
    private static final int MODE_DOZE_BRIGHTNESS = 25;
    private static final int COOKIE = 255;

    private static final int DOZE_TO_NORMAL = 0;
    private static final int DOZE_BRIGHTNESS_HIGH = 1;
    private static final int DOZE_BRIGHTNESS_LOW = 2;

    private static final String SENSOR_TYPE_AOD = "xiaomi.sensor.aod";
    private static final float AOD_LIGHT_BRIGHT = 4f;

    private final DisplayManager mDisplayManager;
    private final SensorManager mSensorManager;
    private final Sensor mSensor;
    private final Handler mHandler = new Handler(Looper.getMainLooper());

    private int mDisplayState = Display.STATE_UNKNOWN;
    private boolean mListening;
    private boolean mBright = true;

    AodBrightness(Context context) {
        mDisplayManager = context.getSystemService(DisplayManager.class);
        mSensorManager = context.getSystemService(SensorManager.class);
        Sensor sensor = null;
        for (Sensor s : mSensorManager.getSensorList(Sensor.TYPE_ALL)) {
            if (SENSOR_TYPE_AOD.equals(s.getStringType()) && s.isWakeUpSensor()) {
                sensor = s;
                break;
            }
        }
        mSensor = sensor;
        mDisplayManager.registerDisplayListener(this, mHandler);
        onDisplayChanged(Display.DEFAULT_DISPLAY);
    }

    @Override
    public void onDisplayAdded(int displayId) {}

    @Override
    public void onDisplayRemoved(int displayId) {}

    @Override
    public void onDisplayChanged(int displayId) {
        if (displayId != Display.DEFAULT_DISPLAY) {
            return;
        }
        int state = mDisplayManager.getDisplay(Display.DEFAULT_DISPLAY).getState();
        if (state == mDisplayState) {
            return;
        }
        mDisplayState = state;
        boolean dozing = state == Display.STATE_DOZE || state == Display.STATE_DOZE_SUSPEND;
        if (state == Display.STATE_DOZE) {
            apply(mBright ? DOZE_BRIGHTNESS_HIGH : DOZE_BRIGHTNESS_LOW);
        } else if (!dozing) {
            apply(DOZE_TO_NORMAL);
        }
        listen(dozing);
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        boolean bright = event.values[0] == AOD_LIGHT_BRIGHT;
        if (bright == mBright) {
            return;
        }
        mBright = bright;
        if (mDisplayState == Display.STATE_DOZE) {
            apply(bright ? DOZE_BRIGHTNESS_HIGH : DOZE_BRIGHTNESS_LOW);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {}

    private void listen(boolean listen) {
        if (mSensor == null || listen == mListening) {
            return;
        }
        mListening = listen;
        if (listen) {
            mSensorManager.registerListener(this, mSensor, SensorManager.SENSOR_DELAY_NORMAL,
                    mHandler);
        } else {
            mSensorManager.unregisterListener(this);
        }
    }

    private void apply(int dozeBrightness) {
        VendorService.call(TAG, SERVICE, DESCRIPTOR, TRANSACTION_SET_FEATURE,
                Display.DEFAULT_DISPLAY, MODE_DOZE_BRIGHTNESS, dozeBrightness, COOKIE);
    }
}
