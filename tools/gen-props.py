#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Carry the properties of a stock build.prop over into a device prop file.

The build regenerates vendor/build.prop and odm/etc/build.prop, so the stock
properties have to come from TARGET_{VENDOR,ODM}_PROP. Identity properties
the build writes itself are dropped. For repeated keys the last value wins,
as on the device; "?=" (optional) values only survive if nothing sets the
key for real. import lines are kept as they are. OVERRIDE lists the few
values an AOSP framework needs changed.

usage: gen-props.py <stock build.prop> <partition> > props/<partition>.prop
"""

import re
import sys

# Written by the build from the device tree / product configuration.
# ro.vndk.version must stay unset: with it linkerconfig puts the whole vendor
# in VNDK v34 mode, which breaks the vendor modules built from source here.
DROP = re.compile(r'|'.join([
    r'ro\.product\.(vendor|odm)\.[^.]+',
    r'ro\.(vendor|odm)\.build\..*',
    r'ro\.bootimage\.build\..*',
    r'ro\.board\.(platform|api_level|first_api_level)',
    r'ro\.product\.first_api_level',
    r'ro\.vndk\.version',
    r'ro\.vendor\.api_level',
]))

# Values that have to differ from stock on an AOSP framework.
OVERRIDE = {
    # HyperOS picks its SurfaceFlinger durations per refresh rate
    # (debug.sf.144_fps.*, debug.sf.high_fps.*); AOSP only reads these base
    # keys, which stock tunes for 60 Hz (sf 27.6 ms, app 20 ms). At 144 Hz
    # that makes SurfaceFlinger report 5 acquired buffers, and BLASTBufferQueue
    # then deadlocks in resizeFrameEventHistory(): no client ever draws. Use
    # the stock 144 Hz values as the base instead.
    'debug.sf.early.sf.duration': '11500000',
    'debug.sf.earlyGl.sf.duration': '11500000',
    'debug.sf.late.sf.duration': '11500000',
    'debug.sf.early.app.duration': '8333333',
    'debug.sf.earlyGl.app.duration': '8333333',
    'debug.sf.late.app.duration': '8333333',
}


def main():
    values, order, imports = {}, [], []
    for raw in open(sys.argv[1], encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('import '):
            imports.append(line)
            continue
        optional = '?=' in line.split('=', 1)[0] + '='
        key, _, value = line.partition('?=' if optional else '=')
        key = key.strip()
        if DROP.fullmatch(key):
            continue
        if key not in values:
            order.append(key)
        if optional and key in values and not values[key][1]:
            continue
        values[key] = (value.strip(), optional)

    for key, value in OVERRIDE.items():
        if key in values:
            values[key] = (value, False)

    print(f'# Carried over from the stock {sys.argv[2]} build.prop'
          ' by tools/gen-props.py')
    for line in imports:
        print(line)
    for key in order:
        value, optional = values[key]
        print(f'{key}{"?=" if optional else "="}{value}')


if __name__ == '__main__':
    main()
