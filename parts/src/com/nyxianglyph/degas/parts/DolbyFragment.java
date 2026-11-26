/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.content.Context;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;

import androidx.preference.ListPreference;
import androidx.preference.Preference;
import androidx.preference.PreferenceCategory;
import androidx.preference.PreferenceFragmentCompat;
import androidx.preference.PreferenceScreen;
import androidx.preference.SeekBarPreference;
import androidx.preference.SwitchPreferenceCompat;

import java.util.Arrays;

/**
 * The Dolby settings: on or off, the profile, and the settings of the profile
 * that is selected. Nothing is kept here; every value is read from the effect
 * and every change goes to {@link Dolby}, which also remembers it.
 */
public class DolbyFragment extends PreferenceFragmentCompat {
    // The equalizer of the effect has twenty bands. Ten sliders are enough to
    // shape a sound; each moves two neighbouring bands.
    private static final int SLIDERS = Dolby.EQUALIZER_BANDS / 2;
    private static final int SLIDER_RANGE = 10;
    // What one step of a slider is in the unit of the effect (1/16 dB).
    private static final int SLIDER_STEP = 16;

    private static final int[][] PRESETS = {
            {0, 0, 0, 0, 0, 0, 0, 0, 0, 0},
            {6, 5, 4, 2, 0, 0, 0, 0, 0, 0},
            {0, 0, 0, 0, 0, 1, 2, 4, 5, 6},
            {-2, -1, 0, 2, 4, 4, 3, 1, 0, -1},
            {5, 4, 2, 0, -2, -2, 0, 2, 4, 5},
    };
    private static final int PRESET_CUSTOM = PRESETS.length;

    private static final int DIALOGUE_AMOUNT_MAX = 12;

    private final Handler mHandler = new Handler(Looper.getMainLooper());
    private Dolby mDolby;

    private SwitchPreferenceCompat mEnabled;
    private ListPreference mProfile;
    private PreferenceCategory mSound;
    private PreferenceCategory mEqualizer;
    private SwitchPreferenceCompat mBass;
    private SwitchPreferenceCompat mDialogue;
    private SeekBarPreference mDialogueAmount;
    private SwitchPreferenceCompat mLeveler;
    private SwitchPreferenceCompat mSpeakerVirtualizer;
    private SwitchPreferenceCompat mHeadphoneVirtualizer;
    private ListPreference mPreset;
    private final SeekBarPreference[] mBands = new SeekBarPreference[SLIDERS];
    private Preference mReset;

    @Override
    public void onCreatePreferences(Bundle savedInstanceState, String rootKey) {
        mDolby = Dolby.get();
        Context context = getPreferenceManager().getContext();
        PreferenceScreen screen = getPreferenceManager().createPreferenceScreen(context);
        setPreferenceScreen(screen);

        mEnabled = new SwitchPreferenceCompat(context);
        mEnabled.setTitle(R.string.dolby_enable);
        mEnabled.setOnPreferenceChangeListener((preference, value) -> {
            mDolby.setEnabled((Boolean) value);
            // Shown once the preference has taken its new value.
            mHandler.post(this::load);
            return true;
        });
        add(screen, "enabled", mEnabled);

        mProfile = new ListPreference(context);
        mProfile.setTitle(R.string.dolby_profile);
        mProfile.setDialogTitle(R.string.dolby_profile);
        mProfile.setEntries(R.array.dolby_profile_names);
        mProfile.setEntryValues(new String[] {
                String.valueOf(Dolby.PROFILE_DYNAMIC),
                String.valueOf(Dolby.PROFILE_MOVIE),
                String.valueOf(Dolby.PROFILE_MUSIC),
        });
        mProfile.setSummaryProvider(ListPreference.SimpleSummaryProvider.getInstance());
        mProfile.setOnPreferenceChangeListener((preference, value) -> {
            mDolby.setProfile(Integer.parseInt((String) value));
            mHandler.post(this::load);
            return true;
        });
        add(screen, "profile", mProfile);

        mSound = new PreferenceCategory(context);
        mSound.setTitle(R.string.dolby_sound);
        add(screen, "sound", mSound);
        mBass = addSwitch(mSound, R.string.dolby_bass, 0, Dolby.BASS_ENHANCER);
        mDialogue = addSwitch(mSound, R.string.dolby_dialogue, 0, Dolby.DIALOGUE_ENHANCER);
        mDialogueAmount = new SeekBarPreference(context);
        mDialogueAmount.setTitle(R.string.dolby_dialogue_amount);
        mDialogueAmount.setMin(1);
        mDialogueAmount.setMax(DIALOGUE_AMOUNT_MAX);
        mDialogueAmount.setShowSeekBarValue(true);
        mDialogueAmount.setOnPreferenceChangeListener((preference, value) -> {
            mDolby.setSetting(mDolby.getProfile(), Dolby.DIALOGUE_ENHANCER_AMOUNT,
                    (Integer) value);
            return true;
        });
        add(mSound, "dialogue_amount", mDialogueAmount);
        mLeveler = addSwitch(mSound, R.string.dolby_leveler, R.string.dolby_leveler_summary,
                Dolby.VOLUME_LEVELER);
        mSpeakerVirtualizer = addSwitch(mSound, R.string.dolby_speaker_virtualizer, 0,
                Dolby.SPEAKER_VIRTUALIZER);
        mHeadphoneVirtualizer = addSwitch(mSound, R.string.dolby_headphone_virtualizer, 0,
                Dolby.HEADPHONE_VIRTUALIZER);

        mEqualizer = new PreferenceCategory(context);
        mEqualizer.setTitle(R.string.dolby_equalizer);
        add(screen, "equalizer", mEqualizer);
        mPreset = new ListPreference(context);
        mPreset.setTitle(R.string.dolby_preset);
        mPreset.setDialogTitle(R.string.dolby_preset);
        mPreset.setEntries(R.array.dolby_preset_names);
        String[] presetValues = new String[PRESETS.length];
        for (int i = 0; i < PRESETS.length; i++) {
            presetValues[i] = String.valueOf(i);
        }
        mPreset.setEntryValues(presetValues);
        mPreset.setOnPreferenceChangeListener((preference, value) -> {
            int preset = Integer.parseInt((String) value);
            setSliders(PRESETS[preset]);
            storeEqualizer();
            mPreset.setSummary(mPreset.getEntries()[preset]);
            return true;
        });
        add(mEqualizer, "preset", mPreset);
        for (int i = 0; i < SLIDERS; i++) {
            SeekBarPreference band = new SeekBarPreference(context);
            band.setTitle(getString(R.string.dolby_band, i + 1));
            band.setMin(-SLIDER_RANGE);
            band.setMax(SLIDER_RANGE);
            band.setShowSeekBarValue(true);
            final int index = i;
            band.setOnPreferenceChangeListener((preference, value) -> {
                int[] sliders = getSliders();
                sliders[index] = (Integer) value;
                storeEqualizer(sliders);
                showPreset(sliders);
                return true;
            });
            mBands[i] = band;
            add(mEqualizer, "band" + i, band);
        }

        mReset = new Preference(context);
        mReset.setTitle(R.string.dolby_reset);
        mReset.setSummary(R.string.dolby_reset_summary);
        mReset.setOnPreferenceClickListener(preference -> {
            mDolby.resetProfile(mDolby.getProfile());
            load();
            return true;
        });
        add(screen, "reset", mReset);

        load();
    }

    @Override
    public void onResume() {
        super.onResume();
        // The tile may have changed the switch meanwhile.
        load();
    }

    // Every preference needs a key: the list dialogs find their preference
    // by it, and the screen restores its position by it.
    private static void add(androidx.preference.PreferenceGroup group, String key,
            Preference preference) {
        preference.setKey(key);
        preference.setPersistent(false);
        preference.setIconSpaceReserved(false);
        group.addPreference(preference);
    }

    private SwitchPreferenceCompat addSwitch(PreferenceCategory category, int title, int summary,
            int setting) {
        SwitchPreferenceCompat preference =
                new SwitchPreferenceCompat(getPreferenceManager().getContext());
        preference.setTitle(title);
        if (summary != 0) {
            preference.setSummary(summary);
        }
        preference.setOnPreferenceChangeListener((changed, value) -> {
            mDolby.setSetting(mDolby.getProfile(), setting, (Boolean) value ? 1 : 0);
            if (setting == Dolby.DIALOGUE_ENHANCER) {
                mDialogueAmount.setEnabled((Boolean) value);
            }
            return true;
        });
        add(category, "setting" + setting, preference);
        return preference;
    }

    /** Shows what the effect holds for the selected profile. */
    private void load() {
        if (mDolby == null) {
            getPreferenceScreen().setEnabled(false);
            return;
        }
        boolean enabled = mDolby.isEnabled();
        int profile = mDolby.getProfile();
        mEnabled.setChecked(enabled);
        mProfile.setValue(String.valueOf(profile));

        int[] equalizer = mDolby.getSetting(profile, Dolby.EQUALIZER_GAINS,
                Dolby.EQUALIZER_BANDS);
        boolean readable = enabled && equalizer != null;
        mProfile.setEnabled(readable);
        mSound.setEnabled(readable);
        mEqualizer.setEnabled(readable);
        mReset.setEnabled(readable);
        if (!readable) {
            return;
        }

        mBass.setChecked(isOn(profile, Dolby.BASS_ENHANCER));
        mDialogue.setChecked(isOn(profile, Dolby.DIALOGUE_ENHANCER));
        mDialogueAmount.setEnabled(mDialogue.isChecked());
        mDialogueAmount.setValue(Math.max(1, Math.min(DIALOGUE_AMOUNT_MAX,
                value(profile, Dolby.DIALOGUE_ENHANCER_AMOUNT))));
        mLeveler.setChecked(isOn(profile, Dolby.VOLUME_LEVELER));
        mSpeakerVirtualizer.setChecked(isOn(profile, Dolby.SPEAKER_VIRTUALIZER));
        mHeadphoneVirtualizer.setChecked(isOn(profile, Dolby.HEADPHONE_VIRTUALIZER));

        int[] sliders = new int[SLIDERS];
        for (int i = 0; i < SLIDERS; i++) {
            int gain = (equalizer[2 * i] + equalizer[2 * i + 1]) / 2;
            sliders[i] = Math.max(-SLIDER_RANGE,
                    Math.min(SLIDER_RANGE, Math.round((float) gain / SLIDER_STEP)));
        }
        setSliders(sliders);
        showPreset(sliders);
    }

    private int value(int profile, int setting) {
        int[] values = mDolby.getSetting(profile, setting, 1);
        return values == null ? 0 : values[0];
    }

    private boolean isOn(int profile, int setting) {
        return value(profile, setting) != 0;
    }

    private int[] getSliders() {
        int[] sliders = new int[SLIDERS];
        for (int i = 0; i < SLIDERS; i++) {
            sliders[i] = mBands[i].getValue();
        }
        return sliders;
    }

    private void setSliders(int[] sliders) {
        for (int i = 0; i < SLIDERS; i++) {
            mBands[i].setValue(sliders[i]);
        }
    }

    private void storeEqualizer() {
        storeEqualizer(getSliders());
    }

    private void storeEqualizer(int[] sliders) {
        int[] gains = new int[Dolby.EQUALIZER_BANDS];
        for (int i = 0; i < SLIDERS; i++) {
            gains[2 * i] = sliders[i] * SLIDER_STEP;
            gains[2 * i + 1] = sliders[i] * SLIDER_STEP;
        }
        mDolby.setSetting(mDolby.getProfile(), Dolby.EQUALIZER_GAINS, gains);
    }

    private void showPreset(int[] sliders) {
        int preset = PRESET_CUSTOM;
        for (int i = 0; i < PRESETS.length; i++) {
            if (Arrays.equals(PRESETS[i], sliders)) {
                preset = i;
                break;
            }
        }
        if (preset == PRESET_CUSTOM) {
            mPreset.setValue(null);
            mPreset.setSummary(R.string.dolby_preset_custom);
        } else {
            mPreset.setValue(String.valueOf(preset));
            mPreset.setSummary(mPreset.getEntries()[preset]);
        }
    }
}
