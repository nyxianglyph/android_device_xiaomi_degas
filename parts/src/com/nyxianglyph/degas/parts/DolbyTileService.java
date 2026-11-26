/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** Quick settings tile that turns the Dolby processing on and off. */
public class DolbyTileService extends TileService {
    @Override
    public void onStartListening() {
        update();
    }

    @Override
    public void onClick() {
        Dolby dolby = Dolby.get();
        if (dolby != null) {
            dolby.setEnabled(!dolby.isEnabled());
        }
        update();
    }

    private void update() {
        Tile tile = getQsTile();
        if (tile == null) {
            return;
        }
        Dolby dolby = Dolby.get();
        if (dolby == null) {
            tile.setState(Tile.STATE_UNAVAILABLE);
        } else {
            tile.setState(dolby.isEnabled() ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        }
        tile.updateTile();
    }
}
