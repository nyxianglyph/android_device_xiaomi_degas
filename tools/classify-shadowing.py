#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Classify the stock files that clash with source modules at install time.

Run after a build failed with "overriding commands for target" errors: every
install path that both a vendor/xiaomi/degas prebuilt and a source module
write is looked up in the source tree and classified (see the header of
stock-shadow-classes.txt).

usage: tools/classify-shadowing.py <android top> > stock-shadow-classes.txt
"""

import os
import re
import sys

top = sys.argv[1]
installs = os.path.join(top, 'out/soong/installs-lineage_degas.mk')
rule = re.compile(r'^out/target/product/[^/]+/(\S+): (\S+)')
interm = re.compile(r'out/soong/\.intermediates/(.+?)/android_[^/]+/')


def module_block(bpdir, name):
    path = os.path.join(top, bpdir, 'Android.bp')
    if not os.path.exists(path):
        return None, None
    s = open(path).read()
    for m in re.finditer(r'(\w+)\s*\{', s):
        start, depth, i = m.end(), 1, m.end()
        while depth and i < len(s):
            depth += {'{': 1, '}': -1}.get(s[i], 0)
            i += 1
        body = s[start:i]
        if re.search(r'^\s*name:\s*"%s"' % re.escape(name), body, re.M):
            return m.group(1), body
    return None, None


sources = {}
with open(installs) as f:
    for line in f:
        m = rule.match(line)
        if m:
            src = interm.search(m.group(2))
            if src:
                sources.setdefault(m.group(1), set()).add(src.group(1))

out = set()
for path, srcs in sources.items():
    ours = [s for s in srcs if s.startswith('vendor/xiaomi/degas/')]
    theirs = [s for s in srcs if not s.startswith('vendor/xiaomi/degas/')]
    if not ours or not theirs:
        continue
    bpdir, mod = os.path.split(theirs[0])
    kind, body = module_block(bpdir, mod)
    if body is None:
        kind, body = module_block(bpdir, re.sub(r'-(V\d+-)?(ndk|cpp|ndk_platform)$', '', mod))
    if body is None and '@' in mod and re.match(r'(frameworks/)?hardware/interfaces', bpdir):
        kind = 'hidl_interface'
    name = re.sub(r'\.so$', '', os.path.basename(path))
    if body is not None and re.search(
            r'^\s*(vendor|soc_specific|proprietary|device_specific):\s*true', body, re.M):
        # Same module name: the prefer'd prebuilt wins; otherwise build it.
        cls = 'vendor' if mod == name else 'source'
    elif kind in ('hidl_interface', 'aidl_interface'):
        cls = 'interface'
    elif '/bin/' in path:
        cls = 'source'
    else:
        cls = 'v34'
    out.add((cls, name))

for cls, name in sorted(out):
    print(cls, name)
