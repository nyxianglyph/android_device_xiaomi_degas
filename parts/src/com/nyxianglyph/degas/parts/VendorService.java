/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

package com.nyxianglyph.degas.parts;

import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.ServiceManager;
import android.util.Log;

/** A call to one of the stock vendor services whose arguments are all ints. */
final class VendorService {
    private VendorService() {}

    static boolean call(String tag, String service, String descriptor, int transaction,
            int... args) {
        IBinder binder = ServiceManager.getService(service);
        if (binder == null) {
            Log.w(tag, service + " is not there");
            return false;
        }
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(descriptor);
            for (int arg : args) {
                data.writeInt(arg);
            }
            binder.transact(transaction, data, reply, 0);
            reply.readException();
            return true;
        } catch (RemoteException | RuntimeException e) {
            Log.e(tag, "call " + transaction + " to " + service + " failed", e);
            return false;
        } finally {
            data.recycle();
            reply.recycle();
        }
    }
}
