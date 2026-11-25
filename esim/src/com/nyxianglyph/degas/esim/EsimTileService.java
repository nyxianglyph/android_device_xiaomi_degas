/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.esim;

import android.app.AlertDialog;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.ServiceManager;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.telephony.TelephonyManager;
import android.telephony.UiccSlotInfo;
import android.util.Log;

/**
 * The second SIM slot of this phone is either the card tray or the built-in
 * eSIM chip; the modem switches between the two. This tile shows which one it
 * is and asks the modem to change, the same way the stock ROM does: a vendor
 * request to the SIM 2 radio service.
 */
public class EsimTileService extends TileService {
    private static final String TAG = "DegasEsim";

    private static final int ESIM_SLOT = 1;
    private static final String SERVICE =
            "vendor.mediatek.hardware.mtkradioex.modem.IMtkRadioExModem/slot2";
    private static final String DESCRIPTOR =
            "vendor.mediatek.hardware.mtkradioex.modem.IMtkRadioExModem";
    // oneway void sendRequestStrings(int serial, in String[] data, int type)
    private static final int TRANSACTION_SEND_REQUEST_STRINGS = IBinder.FIRST_CALL_TRANSACTION + 10;
    private static final String REQUEST_SET_ESIM_STATE = "MIPC_SET_ESIM_STATE";

    private static final long REFRESH_DELAY_MS = 3000;

    private final Handler mHandler = new Handler(Looper.getMainLooper());

    @Override
    public void onStartListening() {
        refresh();
    }

    @Override
    public void onStopListening() {
        mHandler.removeCallbacksAndMessages(null);
    }

    @Override
    public void onClick() {
        final boolean toEsim = !isEsimSelected();
        showDialog(new AlertDialog.Builder(this)
                .setMessage(toEsim ? R.string.dialog_to_esim : R.string.dialog_to_card)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(android.R.string.ok, (dialog, which) -> {
                    select(toEsim);
                    mHandler.postDelayed(this::refresh, REFRESH_DELAY_MS);
                })
                .create());
    }

    private void refresh() {
        Tile tile = getQsTile();
        if (tile == null) {
            return;
        }
        boolean esim = isEsimSelected();
        tile.setState(esim ? Tile.STATE_ACTIVE : Tile.STATE_INACTIVE);
        tile.setSubtitle(getString(esim ? R.string.tile_esim : R.string.tile_card));
        tile.updateTile();
    }

    private boolean isEsimSelected() {
        UiccSlotInfo[] slots = getSystemService(TelephonyManager.class).getUiccSlotsInfo();
        return slots != null && slots.length > ESIM_SLOT && slots[ESIM_SLOT] != null
                && slots[ESIM_SLOT].getIsEuicc();
    }

    private void select(boolean esim) {
        IBinder service = ServiceManager.getService(SERVICE);
        if (service == null) {
            Log.w(TAG, "radio service of SIM 2 is not there");
            return;
        }
        Parcel data = Parcel.obtain();
        try {
            data.writeInterfaceToken(DESCRIPTOR);
            data.writeInt(0);
            data.writeStringArray(new String[] {REQUEST_SET_ESIM_STATE, esim ? "1" : "0"});
            data.writeInt(0);
            service.transact(TRANSACTION_SEND_REQUEST_STRINGS, data, null, IBinder.FLAG_ONEWAY);
        } catch (RemoteException | RuntimeException e) {
            Log.e(TAG, "selecting " + (esim ? "the eSIM" : "the card") + " failed", e);
        } finally {
            data.recycle();
        }
    }
}
