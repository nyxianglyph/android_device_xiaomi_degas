/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.nroption;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.ServiceManager;
import android.os.SystemClock;
import android.util.Log;

/**
 * Lets the modem use 5G standalone as well as non-standalone.
 *
 * MediaTek's modem keeps an NR option of its own (AT+E5GOPT). On stock it is
 * set by MediaTek's telephony framework; AOSP telephony never sets it, and the
 * modem of some phones then starts with standalone 5G off, which leaves them
 * on LTE where the network offers 5G only as standalone.
 */
public class BootReceiver extends BroadcastReceiver {
    private static final String TAG = "NrOption";

    private static final String DESCRIPTOR =
            "vendor.mediatek.hardware.mtkradioex.network.IMtkRadioExNetwork";
    // setNROption(int serial, int option, int reserved)
    private static final int TRANSACTION_SET_NR_OPTION = 53;
    // LTE, NSA and SA: the value MediaTek's framework sets with NR enabled.
    private static final int NR_OPTION_ALL = 7;
    private static final int SLOTS = 2;
    private static final long WAIT_MS = 60_000;

    private static boolean sDone;

    @Override
    public void onReceive(Context context, Intent intent) {
        synchronized (BootReceiver.class) {
            if (sDone) return;
            sDone = true;
        }
        final PendingResult result = goAsync();
        new Thread(() -> {
            try {
                for (int slot = 1; slot <= SLOTS; slot++) {
                    setNrOption(slot);
                }
            } finally {
                result.finish();
            }
        }, TAG).start();
    }

    private static void setNrOption(int slot) {
        final String name = DESCRIPTOR + "/slot" + slot;
        final long end = SystemClock.elapsedRealtime() + WAIT_MS;
        IBinder binder;
        while ((binder = ServiceManager.checkService(name)) == null) {
            if (SystemClock.elapsedRealtime() > end) {
                Log.w(TAG, name + " not found");
                return;
            }
            SystemClock.sleep(1000);
        }
        final Parcel data = Parcel.obtain(binder);
        final Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(DESCRIPTOR);
            data.writeInt(0);
            data.writeInt(NR_OPTION_ALL);
            data.writeInt(0);
            binder.transact(TRANSACTION_SET_NR_OPTION, data, reply, 0);
            Log.i(TAG, "slot " + slot + ": NR option " + NR_OPTION_ALL);
        } catch (RemoteException e) {
            Log.w(TAG, "slot " + slot + ": " + e);
        } finally {
            data.recycle();
            reply.recycle();
        }
    }
}
