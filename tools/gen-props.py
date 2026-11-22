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
key for real. import lines are kept as they are.

usage: gen-props.py <stock build.prop> <partition> > props/<partition>.prop
"""

import re
import sys

# Written by the build from the device tree / product configuration.
DROP = re.compile(r'|'.join([
    r'ro\.product\.(vendor|odm)\.[^.]+',
    r'ro\.(vendor|odm)\.build\..*',
    r'ro\.bootimage\.build\..*',
    r'ro\.board\.(platform|api_level|first_api_level)',
    r'ro\.product\.first_api_level',
    r'ro\.vndk\.version',
    r'ro\.vendor\.api_level',
]))


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

    print(f'# Carried over from the stock {sys.argv[2]} build.prop'
          ' by tools/gen-props.py')
    for line in imports:
        print(line)
    for key in order:
        value, optional = values[key]
        print(f'{key}{"?=" if optional else "="}{value}')


if __name__ == '__main__':
    main()
