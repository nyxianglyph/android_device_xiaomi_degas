#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Install the VNDK v34 libraries that some stock blobs cannot do without.

Most stock vendor and odm blobs run fine on the vendor variants of today's
VNDK libraries (device.mk), and hardware/lineage/compat covers others with
shims and its own -v34 copies (libui-v34). A few still use symbols nothing
exports any more
(tools/check-vendor-deps.py lists them as "needs v34"). Those get the v34
prebuilt as <name>-v34.so, with its SONAME and its links to the other copied
libraries renamed, so both versions can live in one process; extract-files.py
points the users at the -v34 names.

usage: tools/gen-vndk-v34.py
"""

import os
import shutil
import subprocess

here = os.path.dirname(os.path.abspath(__file__))
top = os.path.join(here, '../../../..')
src = os.path.join(top, 'prebuilts/vndk/v34/arm64/arch-arm64-armv8-a/shared')
dst = os.path.join(here, '../prebuilt/vndk-v34/lib64')
patchelf = os.path.join(top, 'prebuilts/extract-tools/linux-x86/bin/patchelf-0_18')

# Keep in sync with VNDK_V34_USERS in extract-files.py.
LIBS = [
    'libbase',
    'libcrypto',
    'libssl',
    'libstagefright_bufferqueue_helper',
]


def needed(path):
    out = subprocess.run(['readelf', '-dW', path], capture_output=True, text=True).stdout
    return [l.split('[')[1].rstrip(']') for l in out.splitlines() if '(NEEDED)' in l]


def main():
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    # libui-v34 comes from hardware/lineage/compat.
    names = {f'{l}.so' for l in LIBS + ['libui']}
    for lib in LIBS:
        for sub in ('vndk-core', 'vndk-sp'):
            path = os.path.join(src, sub, f'{lib}.so')
            if os.path.exists(path):
                break
        else:
            raise SystemExit(f'{lib} is not a VNDK v34 library')
        out = os.path.join(dst, f'{lib}-v34.so')
        shutil.copyfile(path, out)
        args = ['--set-soname', f'{lib}-v34.so']
        for dep in needed(out):
            if dep in names:
                args += ['--replace-needed', dep, dep[:-3] + '-v34.so']
        subprocess.run([patchelf, *args, out], check=True)
        print(f'{lib}-v34.so')


if __name__ == '__main__':
    main()
