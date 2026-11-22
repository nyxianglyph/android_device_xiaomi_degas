#!/usr/bin/env -S PYTHONPATH=../../../tools/extract-utils python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#

from extract_utils.fixups_blob import (
    blob_fixup,
    blob_fixups_user_type,
)
from extract_utils.fixups_lib import (
    lib_fixup_remove,
    lib_fixups,
    lib_fixups_user_type,
)
from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

import os
import subprocess
import sys

namespace_imports = [
    'device/xiaomi/degas',
]

here = os.path.dirname(os.path.abspath(__file__))

# How stock files named like a source module are handled (interface, source,
# vendor, v34), see stock-shadow-classes.txt and tools/classify-shadowing.py.
with open(os.path.join(here, 'stock-shadow-classes.txt')) as f:
    shadow_classes = dict(reversed(l.split()) for l in f
                          if l.strip() and not l.startswith('#'))
v34_libs = tuple(sorted(n for n, c in shadow_classes.items() if c == 'v34'))

# The other stock libraries sharing their name with a (system-only) source
# module are kept as the stock binaries under <name>_vendor (see
# tools/find-source-overlap.sh); the stock blobs link against those.
with open(os.path.join(here, 'stock-libs-shadowing-source.txt')) as f:
    stock_shadowing = tuple(l.strip() for l in f
                            if l.strip() and l.strip() not in shadow_classes)


def lib_fixup_stock_vendor(lib: str, partition: str, *args, **kwargs):
    return f'{lib}_vendor' if partition in ('vendor', 'odm') else None


# The stock vendor gets these from the com.android.vndk.v34 APEX at runtime, as
# on HyperOS; they must not be built into the vendor partition as well.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..',
                       'prebuilts/vndk/v34/arm64/configs/module_names.txt')) as f:
    vndk_v34 = tuple(sorted(
        {l.split()[1] for l in f if l.strip()}
        - set(stock_shadowing) - set(v34_libs)))


def lib_fixup_vndk_v34(lib: str, partition: str, *args, **kwargs):
    return lib_fixup_remove(lib) if partition in ('vendor', 'odm') else None


def lib_fixup_v34(lib: str, partition: str, *args, **kwargs):
    return f'{lib}-v34' if partition in ('vendor', 'odm') else None


# The same for the MediaTek IMS libraries taken from system_ext.
def lib_fixup_stock_system_ext(lib: str, partition: str, *args, **kwargs):
    return f'{lib}_system_ext' if partition == 'system_ext' else None


lib_fixups: lib_fixups_user_type = {
    **lib_fixups,
    stock_shadowing: lib_fixup_stock_vendor,
    vndk_v34: lib_fixup_vndk_v34,
    v34_libs: lib_fixup_v34,
    ('libsink',): lib_fixup_stock_system_ext,
}


def v34_users(dump):
    """Stock vendor/odm ELFs that need a library renamed to <name>-v34.so."""
    names = {f'{n}.so' for n in v34_libs}
    users = {}
    with open(os.path.join(here, 'proprietary-files.txt')) as f:
        # (stock path, installed path); fixups are keyed by the installed one.
        entries = [(l.strip().split(';')[0].split(':') * 2)[:2] for l in f
                   if l.strip() and not l.startswith('#')]
    for src, rel in entries:
        if not src.startswith(('vendor/', 'odm/')):
            continue
        path = os.path.join(dump, src)
        with open(path, 'rb') as e:
            data = e.read()
        if data[:4] != b'\x7fELF' or not any(b'\0' + n.encode() + b'\0' in data for n in names):
            continue
        out = subprocess.run(['readelf', '-d', path], capture_output=True, text=True).stdout
        needed = {l.split('[')[1].split(']')[0] for l in out.splitlines() if '(NEEDED)' in l}
        hits = tuple(sorted(needed & names))
        if hits:
            users.setdefault(hits, []).append(rel)
    return users


def v34_blob_fixups():
    dump = next((a for a in sys.argv[1:] if os.path.isdir(a)), None)
    if dump is None:
        return {}
    fixups = {}
    for hits, rels in v34_users(dump).items():
        fixup = blob_fixup()
        for name in hits:
            fixup = fixup.replace_needed(name, name[:-3] + '-v34.so')
        fixups[tuple(rels)] = fixup
    return fixups


blob_fixups: blob_fixups_user_type = {
    **v34_blob_fixups(),
}  # fmt: skip

module = ExtractUtilsModule(
    'degas',
    'xiaomi',
    blob_fixups=blob_fixups,
    lib_fixups=lib_fixups,
    namespace_imports=namespace_imports,
)

if __name__ == '__main__':
    utils = ExtractUtils.device(module)
    utils.run()
