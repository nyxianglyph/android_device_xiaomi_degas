/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.content.Context;
import android.content.SharedPreferences;
import android.media.AudioManager;
import android.media.audiofx.AudioEffect;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import java.util.Map;
import java.util.UUID;

/**
 * Keeps the Dolby processing of the stock audio HAL in use.
 *
 * The speakers and the headphone output of this phone are tuned with Dolby's
 * effect on the output mix; without it the sound is noticeably thinner than
 * on the stock system. The effect and its service are in the vendor image,
 * but an effect only runs while somebody holds it, and it forgets what it was
 * told when the audio server restarts. The stock system holds it from an app
 * of its own. This holds it instead and gives it the settings again whenever
 * it comes up: on or off, the profile, and what was changed in a profile.
 */
final class Dolby {
    private static final String TAG = "DegasDolby";

    static final int PROFILE_DYNAMIC = 0;
    static final int PROFILE_MOVIE = 1;
    static final int PROFILE_MUSIC = 2;

    // Settings every profile has for itself.
    static final int HEADPHONE_VIRTUALIZER = 101;
    static final int SPEAKER_VIRTUALIZER = 102;
    static final int VOLUME_LEVELER = 103;
    static final int DIALOGUE_ENHANCER = 105;
    static final int DIALOGUE_ENHANCER_AMOUNT = 108;
    static final int EQUALIZER_GAINS = 110;
    static final int BASS_ENHANCER = 111;

    static final int EQUALIZER_BANDS = 20;

    private static final UUID EFFECT_DAP =
            UUID.fromString("9d4921da-8225-4f29-aefa-39537a04bcaa");
    private static final int OUTPUT_MIX = 0;
    private static final int PRIORITY = 0;

    // The protocol of the effect. A value is set with PARAM_VALUES and
    // {parameter, number of values, values}; it is read with
    // PARAM_VALUES + parameter. A setting of a profile is set as the values
    // {profile, setting, values} of PARAM_SET_PROFILE_SETTING and read with
    // (setting << 16) + (profile << 8) + PARAM_GET_PROFILE_SETTING.
    private static final int PARAM_VALUES = 5;
    private static final int PARAM_ON = 0;
    private static final int PARAM_PROFILE = 0xA000000;
    private static final int PARAM_SET_PROFILE_SETTING = 0x1000000;
    private static final int PARAM_GET_PROFILE_SETTING = 0x1000005;
    private static final int PARAM_RESET_PROFILE = 0xC000000;

    private static final String PREFERENCES = "dolby";
    private static final String KEY_ENABLED = "enabled";
    private static final String KEY_PROFILE = "profile";
    // "setting.<profile>.<setting>" holds the changed values, comma separated.
    private static final String KEY_SETTING = "setting.";

    private static final int RETRY_MS = 2000;

    private static Dolby sInstance;

    private final SharedPreferences mPreferences;
    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private final Runnable mApply = this::apply;
    private AudioEffect mEffect;

    static Dolby get() {
        return sInstance;
    }

    Dolby(Context context) {
        sInstance = this;
        mPreferences = context.createDeviceProtectedStorageContext()
                .getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
        context.getSystemService(AudioManager.class).setAudioServerStateCallback(
                context.getMainExecutor(), new AudioManager.AudioServerStateCallback() {
                    @Override
                    public void onAudioServerDown() {
                        release();
                    }

                    @Override
                    public void onAudioServerUp() {
                        apply();
                    }
                });
        apply();
    }

    boolean isEnabled() {
        return mPreferences.getBoolean(KEY_ENABLED, true);
    }

    void setEnabled(boolean enabled) {
        mPreferences.edit().putBoolean(KEY_ENABLED, enabled).apply();
        apply();
    }

    int getProfile() {
        return mPreferences.getInt(KEY_PROFILE, PROFILE_DYNAMIC);
    }

    void setProfile(int profile) {
        mPreferences.edit().putInt(KEY_PROFILE, profile).apply();
        apply();
    }

    /** The values of a setting of a profile, or null while the effect is not in use. */
    int[] getSetting(int profile, int setting, int length) {
        if (mEffect == null) {
            return null;
        }
        try {
            byte[] buffer = new byte[(length + 2) * 4];
            mEffect.getParameter(
                    (setting << 16) + (profile << 8) + PARAM_GET_PROFILE_SETTING, buffer);
            int[] values = new int[length];
            for (int i = 0; i < length; i++) {
                values[i] = getInt(buffer, 4 * i);
            }
            return values;
        } catch (RuntimeException e) {
            Log.w(TAG, "read setting " + setting, e);
            return null;
        }
    }

    void setSetting(int profile, int setting, int... values) {
        StringBuilder stored = new StringBuilder();
        for (int value : values) {
            if (stored.length() > 0) stored.append(',');
            stored.append(value);
        }
        mPreferences.edit().putString(KEY_SETTING + profile + "." + setting, stored.toString())
                .apply();
        if (mEffect != null) {
            try {
                writeSetting(profile, setting, values);
            } catch (RuntimeException e) {
                Log.w(TAG, "write setting " + setting, e);
            }
        }
    }

    /** Gives a profile back the settings it came with. */
    void resetProfile(int profile) {
        SharedPreferences.Editor editor = mPreferences.edit();
        for (String key : mPreferences.getAll().keySet()) {
            if (key.startsWith(KEY_SETTING + profile + ".")) {
                editor.remove(key);
            }
        }
        editor.apply();
        if (mEffect != null) {
            try {
                setValue(PARAM_RESET_PROFILE, profile);
            } catch (RuntimeException e) {
                Log.w(TAG, "reset profile " + profile, e);
            }
        }
    }

    private void apply() {
        mHandler.removeCallbacks(mApply);
        try {
            if (!isEnabled()) {
                if (mEffect != null) {
                    setValue(PARAM_ON, 0);
                    mEffect.setEnabled(false);
                }
                release();
                return;
            }
            boolean fresh = mEffect == null;
            if (fresh) {
                mEffect = new AudioEffect(AudioEffect.EFFECT_TYPE_NULL, EFFECT_DAP, PRIORITY,
                        OUTPUT_MIX);
            }
            setValue(PARAM_ON, 1);
            setValue(PARAM_PROFILE, getProfile());
            if (fresh) {
                writeStoredSettings();
            }
            mEffect.setEnabled(true);
        } catch (RuntimeException e) {
            // The audio server may not be up yet.
            Log.w(TAG, "Dolby effect not available, trying again", e);
            release();
            mHandler.postDelayed(mApply, RETRY_MS);
        }
    }

    private void writeStoredSettings() {
        for (Map.Entry<String, ?> entry : mPreferences.getAll().entrySet()) {
            if (!entry.getKey().startsWith(KEY_SETTING)) continue;
            try {
                String[] key = entry.getKey().substring(KEY_SETTING.length()).split("\\.");
                String[] stored = ((String) entry.getValue()).split(",");
                int[] values = new int[stored.length];
                for (int i = 0; i < stored.length; i++) {
                    values[i] = Integer.parseInt(stored[i]);
                }
                writeSetting(Integer.parseInt(key[0]), Integer.parseInt(key[1]), values);
            } catch (RuntimeException e) {
                Log.w(TAG, "stored setting " + entry.getKey(), e);
            }
        }
    }

    private void writeSetting(int profile, int setting, int[] values) {
        byte[] buffer = new byte[(values.length + 4) * 4];
        putInt(buffer, 0, PARAM_SET_PROFILE_SETTING);
        putInt(buffer, 4, values.length + 1);
        putInt(buffer, 8, profile);
        putInt(buffer, 12, setting);
        for (int i = 0; i < values.length; i++) {
            putInt(buffer, 16 + 4 * i, values[i]);
        }
        check(mEffect.setParameter(PARAM_VALUES, buffer), setting);
    }

    private void setValue(int parameter, int value) {
        byte[] buffer = new byte[12];
        putInt(buffer, 0, parameter);
        putInt(buffer, 4, 1);
        putInt(buffer, 8, value);
        check(mEffect.setParameter(PARAM_VALUES, buffer), parameter);
    }

    private static void check(int status, int parameter) {
        if (status != AudioEffect.SUCCESS) {
            throw new IllegalStateException("parameter " + parameter + ": status " + status);
        }
    }

    private static void putInt(byte[] buffer, int offset, int value) {
        for (int i = 0; i < 4; i++) {
            buffer[offset + i] = (byte) (value >> (8 * i));
        }
    }

    private static int getInt(byte[] buffer, int offset) {
        int value = 0;
        for (int i = 0; i < 4; i++) {
            value |= (buffer[offset + i] & 0xff) << (8 * i);
        }
        return value;
    }

    private void release() {
        if (mEffect != null) {
            try {
                mEffect.release();
            } catch (RuntimeException e) {
                Log.w(TAG, "release", e);
            }
            mEffect = null;
        }
    }
}
