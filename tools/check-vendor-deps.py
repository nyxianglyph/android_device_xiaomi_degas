#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Check that every vendor and odm ELF can be linked on the device.

The stock blobs were built against VNDK v34, which this vendor does not run
(see the VNDK block in device.mk). This resolves, on the host, what the
vendor linker namespace would: DT_NEEDED against /vendor and /odm libraries
plus the LLNDK libraries of /system, and then every undefined dynamic symbol
against the libraries each ELF loads. It reports libraries that cannot be
found (add their .vendor variant) and symbols that no loaded library defines
(those need the v34 copy of the library instead).

usage: tools/check-vendor-deps.py <product out dir> [<VNDK v34 shared dir>]

With the VNDK v34 prebuilt dir (prebuilts/vndk/v34/arm64/arch-arm64-armv8-a/
shared), unresolved symbols are attributed to the v34 library exporting them,
and a summary lists which v34 libraries are needed by which ELFs.
"""

import collections
import os
import subprocess
import sys

prod = sys.argv[1]
v34 = {}
if len(sys.argv) > 2:
    for sub in ('vndk-core', 'vndk-sp'):
        d = os.path.join(sys.argv[2], sub)
        for f in os.listdir(d):
            out = subprocess.run(['nm', '-D', '--defined-only', os.path.join(d, f)],
                                 capture_output=True, text=True).stdout
            for l in out.splitlines():
                parts = l.split()
                if len(parts) == 3:
                    v34.setdefault(parts[2].split('@')[0], f)
llndk = {l.strip() for l in open(os.path.join(prod, 'system/etc/llndk.libraries.txt'))
         if l.strip()}

libdirs = {64: [], 32: []}
for part in ('odm', 'vendor'):
    for bits, d in ((64, 'lib64'), (32, 'lib')):
        libdirs[bits] += [os.path.join(prod, part, d), os.path.join(prod, part, d, 'hw'),
                          os.path.join(prod, part, d, 'egl')]
sysdirs = {64: [os.path.join(prod, 'system/lib64')], 32: [os.path.join(prod, 'system/lib')]}
# Libraries in subdirectories (lib64/mt6897, camera plugins, ...) are found
# through RUNPATH or loaded by full path; index them as a fallback.
anywhere = {64: {}, 32: {}}
for part in ('odm', 'vendor'):
    for bits, d in ((64, 'lib64'), (32, 'lib')):
        for root, _, files in os.walk(os.path.join(prod, part, d)):
            for f in files:
                if f.endswith('.so'):
                    anywhere[bits].setdefault(f, os.path.join(root, f))


def elf_bits(path):
    try:
        with open(path, 'rb') as f:
            head = f.read(5)
    except OSError:
        return None
    if head[:4] != b'\x7fELF':
        return None
    return 64 if head[4] == 2 else 32


def needed(path):
    out = subprocess.run(['readelf', '-dW', path], capture_output=True, text=True).stdout
    return [l.split('[')[1].rstrip(']') for l in out.splitlines() if '(NEEDED)' in l]


symcache = {}


def symbols(path):
    """(defined, undefined) dynamic symbols, ignoring weak undefined ones."""
    if path not in symcache:
        out = subprocess.run(['nm', '-D', path], capture_output=True, text=True).stdout
        defined, undefined = set(), set()
        for l in out.splitlines():
            parts = l.split()
            if len(parts) == 3 and parts[1] not in ('U', 'w', 'v'):
                defined.add(parts[2].split('@')[0])
            elif len(parts) == 2 and parts[0] == 'U':
                undefined.add(parts[1].split('@')[0])
        symcache[path] = (defined, undefined)
    return symcache[path]


def find(lib, bits):
    for d in libdirs[bits]:
        p = os.path.join(d, lib)
        if os.path.isfile(p):
            return p
    if lib in anywhere[bits]:
        return anywhere[bits][lib]
    if lib in llndk:
        for d in sysdirs[bits]:
            p = os.path.join(d, lib)
            if os.path.islink(p) and os.readlink(p).startswith('/apex/'):
                p = os.path.join(prod, os.readlink(p).lstrip('/'))  # bionic
            if os.path.isfile(p):
                return p
        return 'LLNDK'  # provided by an APEX the host tree does not unpack
    return None


missing_lib = collections.defaultdict(set)
missing_sym = collections.defaultdict(set)
for part in ('vendor', 'odm'):
    for root, _, files in os.walk(os.path.join(prod, part)):
        for name in files:
            path = os.path.join(root, name)
            if os.path.islink(path):
                continue
            bits = elf_bits(path)
            if bits is None:
                continue
            rel = os.path.relpath(path, prod)
            # Breadth-first load order, like the linker's global group.
            order, queue, seen = [], list(needed(path)), set()
            while queue:
                lib = queue.pop(0)
                if lib in seen:
                    continue
                seen.add(lib)
                where = find(lib, bits)
                if where is None:
                    missing_lib[(bits, lib)].add(rel)
                elif where != 'LLNDK':
                    order.append(where)
                    # LLNDK libraries resolve their own needs in the system
                    # namespace; only follow vendor and odm libraries.
                    if lib not in llndk:
                        queue += needed(where)
            if any(k[1] in seen for k in missing_lib):
                continue  # symbols cannot be judged with a library missing
            provided = set()
            for lib in order:
                provided |= symbols(lib)[0]
            provided |= symbols(path)[0]
            for sym in symbols(path)[1] - provided:
                missing_sym[(bits, rel)].add(sym)

for (bits, lib), users in sorted(missing_lib.items()):
    print(f'missing library {bits}-bit {lib}: {len(users)} users, e.g. {sorted(users)[0]}')
need_v34 = collections.defaultdict(set)
for (bits, rel), syms in sorted(missing_sym.items()):
    libs = sorted({v34[s] for s in syms if s in v34})
    for lib in libs:
        need_v34[(bits, lib)].add(rel)
    print(f'unresolved symbols in {rel}: {" ".join(sorted(syms)[:6])}'
          f'{" ..." if len(syms) > 6 else ""} ({len(syms)})'
          + (f' [v34: {" ".join(libs)}]' if libs else ''))
for (bits, lib), users in sorted(need_v34.items()):
    print(f'needs v34 {bits}-bit {lib}: {" ".join(sorted(users))}')
print(f'{len(missing_lib)} missing libraries, {len(missing_sym)} ELFs with unresolved symbols',
      file=sys.stderr)
