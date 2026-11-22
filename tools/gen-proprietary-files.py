#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Generate proprietary-files.txt from an extracted stock dump.

The stock vendor and odm partitions are taken over as they are; only the
files the Android build generates itself (properties, SELinux policy, VINTF
top-level manifests, fs config, toybox links) and files this tree ships in
their place are left out. Symlinks become ;SYMLINK= entries of their target.

usage: gen-proprietary-files.py <dump> > proprietary-files.txt
       <dump> holds vendor/, odm/ and system_ext/ as on the device.
"""

import os
import re
import sys

# Built or provided by the Android build / this device tree instead.
EXCLUDE = [
    r'(vendor/build|odm/etc/build)\.prop',
    r'(vendor|odm)/etc/selinux/.*',
    r'(vendor|odm)/etc/(fs_config_dirs|fs_config_files|group|passwd|linker\.config\.pb)',
    r'(vendor|odm)/etc/NOTICE.*',
    r'vendor/etc/vintf/(manifest|compatibility_matrix)\.xml',
    r'vendor/etc/fstab\..*',
    r'vendor/bin/(sh|toybox_vendor|toolbox|vndservicemanager)',
    r'vendor/etc/init/vndservicemanager\.rc',
    r'.*/oat/.*',  # dexopt output of the stock framework
    r'vendor/overlay/.*',  # HyperOS RROs; overlay/ holds our own values instead
]

# Pieces of the HyperOS system_ext the MediaTek IMS and telephony stack needs.
SYSTEM_EXT = [
    r'system_ext/framework/mediatek-(ims-base|ims-common|ims-extension-plugin|telecom-common|telephony-base|telephony-common)\.jar',
    r'system_ext/priv-app/ImsService/.*',
    r'system_ext/lib64/libimsma.*\.so',
    r'system_ext/lib64/vendor\.mediatek\.hardware\.videotelephony.*\.so',
    r'system_ext/etc/sysconfig/com\.mediatek\.ims\.config\.xml',
    r'system_ext/etc/permissions/com\.mediatek\.ims.*\.xml',
]

exclude = re.compile('|'.join(f'(?:{e})' for e in EXCLUDE))
system_ext = re.compile('|'.join(f'(?:{e})' for e in SYSTEM_EXT))


def walk(dump, part):
    root = os.path.join(dump, part)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames + [d for d in dirnames if os.path.islink(os.path.join(dirpath, d))]):
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, dump), full


def main():
    dump = sys.argv[1]
    files, links = {}, {}
    for part in ('vendor', 'odm', 'system_ext'):
        for rel, full in walk(dump, part):
            if exclude.fullmatch(rel):
                continue
            if part == 'system_ext' and not system_ext.fullmatch(rel):
                continue
            if os.path.islink(full):
                target = os.readlink(full)
                tgt = os.path.normpath(target.lstrip('/') if target.startswith('/')
                                       else os.path.join(os.path.dirname(rel), target))
                # Links into other partitions or to toybox are not blobs.
                if os.path.isfile(os.path.join(dump, tgt)) and not exclude.fullmatch(tgt):
                    links.setdefault(tgt, []).append(rel)
                continue
            files[rel] = True

    section = None
    for rel in sorted(files):
        top = '/'.join(rel.split('/')[:2])
        if top != section:
            section = top
            print(f'\n# {section}')
        print(rel + ''.join(f';SYMLINK={l}' for l in sorted(links.get(rel, []))))


if __name__ == '__main__':
    main()
