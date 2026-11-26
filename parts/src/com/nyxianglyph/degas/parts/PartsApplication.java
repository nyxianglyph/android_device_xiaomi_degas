/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.app.Application;

/**
 * The few things this phone needs from a process of its own, because the
 * stock HALs expect the system to ask for them: the touch controller's
 * gestures on a dark screen, the panel's brightness on the always-on display,
 * the color scheme and the Dolby sound processing. It is persistent and starts
 * with the system.
 */
public class PartsApplication extends Application {
    private TouchGestures mTouchGestures;
    private AodBrightness mAodBrightness;
    private ColorScheme mColorScheme;
    private Dolby mDolby;

    @Override
    public void onCreate() {
        super.onCreate();
        mTouchGestures = new TouchGestures(this);
        mAodBrightness = new AodBrightness(this);
        mColorScheme = new ColorScheme(this);
        mDolby = new Dolby(this);
    }
}
