#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""List every install path that more than one producer writes.

Kati stops at the first "overriding commands for target" error; this reads
what soong generated (module installs, symlinks, VINTF fragment copies) plus
the PRODUCT_COPY_FILES of the vendor makefile and reports all clashes at
once, so they can be fixed in one go.

usage: tools/check-install-collisions.py <android top>
"""

import collections
import os
import re
import sys

top = sys.argv[1]
product = 'out/target/product/degas/'
producers = collections.defaultdict(set)

install = re.compile(r'^' + re.escape(product) + r'(\S+): (\S+)')
interm = re.compile(r'out/soong/\.intermediates/(.+?)/(?:android|linux)_[^/]+/')
vintf = re.compile(r'copy-vintf-manifest-checked, ([^,]+), ' + re.escape(product) + r'([^)]+)\)')

with open(os.path.join(top, 'out/soong/installs-lineage_degas.mk')) as f:
    for line in f:
        m = install.match(line)
        if m:
            src = interm.search(m.group(2))
            producers[m.group(1)].add('module ' + (src.group(1) if src else m.group(2)))
            continue
        m = vintf.search(line)
        if m:
            producers[m.group(2)].add('vintf ' + m.group(1))

copy = re.compile(r'^\s*(\S+):\$\(TARGET_COPY_OUT_(\w+)\)(\S*)')
for mk in ('vendor/xiaomi/degas/degas-vendor.mk', 'device/xiaomi/degas/device.mk'):
    with open(os.path.join(top, mk)) as f:
        for line in f:
            m = copy.match(line.rstrip(' \\\n'))
            if m:
                part = m.group(2).lower()
                part = {'vendor_ramdisk': 'vendor_ramdisk'}.get(part, part)
                producers[part + m.group(3)].add('copy ' + m.group(1))

clashes = {p: s for p, s in producers.items() if len(s) > 1}
for path in sorted(clashes):
    print(path)
    for s in sorted(clashes[path]):
        print('    ' + s)
print(f'{len(clashes)} clashing install paths', file=sys.stderr)
