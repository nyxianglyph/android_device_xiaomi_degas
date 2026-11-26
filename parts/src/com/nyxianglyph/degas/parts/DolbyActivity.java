/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.os.Bundle;

import com.android.settingslib.collapsingtoolbar.CollapsingToolbarBaseActivity;

/** The Dolby settings, reached from the sound settings and from the tile. */
public class DolbyActivity extends CollapsingToolbarBaseActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (savedInstanceState == null) {
            getSupportFragmentManager().beginTransaction()
                    .replace(com.android.settingslib.collapsingtoolbar.R.id.content_frame,
                            new DolbyFragment())
                    .commit();
        }
    }
}
