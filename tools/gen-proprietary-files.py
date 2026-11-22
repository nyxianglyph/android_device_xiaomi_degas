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

Stock libraries named like a source module (stock-libs-shadowing-source.txt,
see tools/find-source-overlap.sh) get the _vendor module suffix, so the stock
binary is installed instead of the source one.

usage: gen-proprietary-files.py <dump> [<shadowing list>] > proprietary-files.txt
       <dump> holds vendor/, odm/ and system_ext/ as on the device.
"""

import os
import re
import struct
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
    # Glob characters cannot be build paths. The only such stock files are
    # the SR*.dla video super-resolution models of the HyperOS system side,
    # which no vendor component uses.
    r'.*[*?\[\]].*',
]

# Pieces of the HyperOS system_ext the MediaTek IMS and telephony stack needs.
SYSTEM_EXT = [
    # mediatek-{common,telecom-common,telephony-common} are built from
    # hardware/mediatek instead (AOSP-framework builds of the same classes).
    r'system_ext/framework/mediatek-(ims-base|ims-common|ims-extension-plugin|telephony-base)\.jar',
    r'system_ext/priv-app/ImsService/.*',
    r'system_ext/lib64/libimsma.*\.so',
    # Dependency closure of libimsma_rtp.
    r'system_ext/lib64/lib(signal|sink|source|comutils|vcodec_cap|vcodec_capenc|vt_avsync)\.so',
    r'system_ext/lib64/vendor\.mediatek\.hardware\.videotelephony.*\.so',
    r'system_ext/etc/sysconfig/com\.mediatek\.ims\.config\.xml',
    r'system_ext/etc/permissions/com\.mediatek\.ims.*\.xml',
]

# system_ext blobs named like an unrelated source module (see extract-files.py).
SYSTEM_EXT_SHADOWING = {'libsink'}

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

    # Stock files clashing with source modules, see stock-shadow-classes.txt.
    classes = {}
    cls_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                            'stock-shadow-classes.txt')
    if os.path.exists(cls_path):
        for line in open(cls_path):
            if line.strip() and not line.startswith('#'):
                cls, name = line.split()
                classes[name] = cls
    renamed = {}
    for rel in list(files):
        m = re.fullmatch(r'(vendor|odm)/(?:lib(?:64)?/([^/]+)\.so|bin/(?:hw/)?([^/]+))', rel)
        cls = classes.get(m.group(2) or m.group(3)) if m else None
        if cls in ('interface', 'source'):
            del files[rel]
            links.pop(rel, None)
        elif cls == 'v34':
            renamed[rel] = rel[:-3] + '-v34.so'

    suffixes = lib_suffixes(files)
    shadowing = set()
    if len(sys.argv) > 2:
        shadowing = {l.strip() for l in open(sys.argv[2]) if l.strip()}
        for rel in files:
            m = re.fullmatch(r'(vendor|odm)/(?:lib(?:64)?/([^/]+)\.so|bin/(?:hw/)?([^/]+))', rel)
            name = m and (m.group(2) or m.group(3))
            if (m and name in shadowing and rel not in suffixes
                    and classes.get(name) not in ('vendor', 'v34')):
                suffixes[rel] = '_vendor'
    for rel in files:
        m = re.fullmatch(r'system_ext/lib64/([^/]+)\.so', rel)
        if m and m.group(1) in SYSTEM_EXT_SHADOWING:
            suffixes[rel] = '_system_ext'

    have32 = {os.path.basename(r)[:-3] for r in files
              if r.split('/')[1] == 'lib' and r.endswith('.so')}
    unresolvable32 = {r for r in files if r.split('/')[1] in ('lib', 'bin')
                      and any(n in shadowing and n not in have32
                              for n in elf32_needed(os.path.join(dump, r)))}

    section = None
    for rel in sorted(files):
        top = '/'.join(rel.split('/')[:2])
        if top != section:
            section = top
            print(f'\n# {section}')
        args = [f'SYMLINK={l}' for l in sorted(links.get(rel, []))]
        if rel in suffixes:
            args.append(f'MODULE_SUFFIX={suffixes[rel]}')
        if '/etc/vintf/' in rel and shadows_package(rel, shadowing):
            # VINTF files may not be copied either; BoardConfig.mk merges
            # these into the device manifest instead.
            args.append('EXTRACT_ONLY')
        elif is_bin_data(rel, os.path.join(dump, rel)) or shadows_package(rel, shadowing):
            args.append('MAKE_COPY_RULE_ONLY')
        if rel in unresolvable32:
            # The stock file needs a 32-bit library the stock vendor does not
            # have either; it cannot load there, keep it but drop its deps.
            args.append('DISABLE_DEPS')
        if rel in renamed:
            # Installed as <name>-v34.so next to the source build of <name>;
            # extract-files.py points the stock users at the new name.
            print(';'.join([f'{rel}:{renamed[rel]}'] + args + ['FIX_SONAME']))
            continue
        print(';'.join([rel] + args))


def is_elf(path):
    with open(path, 'rb') as f:
        return f.read(4) == b'\x7fELF'


def elf32_needed(path):
    """DT_NEEDED names (without .so) of a 32-bit ELF, [] for anything else."""
    with open(path, 'rb') as f:
        d = f.read()
    if d[:5] != b'\x7fELF\x01':
        return []
    shoff, = struct.unpack_from('<I', d, 0x20)
    shentsize, shnum = struct.unpack_from('<HH', d, 0x2e)
    secs = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
    out = []
    for sec in secs:
        if sec[1] != 6:  # SHT_DYNAMIC
            continue
        strtab = secs[sec[6]][4]
        for off in range(sec[4], sec[4] + sec[5], 8):
            tag, val = struct.unpack_from('<iI', d, off)
            if tag == 0:
                break
            if tag == 1:  # DT_NEEDED
                name = d[strtab + val:d.index(b'\0', strtab + val)].decode()
                out.append(name[:-3] if name.endswith('.so') else name)
    return out


def shadows_package(rel, shadowing):
    # extract_utils names VINTF fragments and jars after the file and ignores
    # MODULE_SUFFIX for them; when a source module has that name, install the
    # stock file as a plain copy to the same path instead.
    name = os.path.basename(rel)
    if '/etc/vintf/' in rel:
        return name in shadowing
    return rel.endswith('.jar') and name[:-4] in shadowing


def is_bin_data(rel, full):
    # extract_utils turns everything below bin/ into a binary package; data
    # files there (camera tuning databases) have to stay plain copies.
    return '/bin/' in rel and not is_elf(full)


def lib_suffixes(files):
    """Give libraries whose stem is taken by another directory a suffix.

    lib/ and lib64/ copies of the same relative path are one multilib module;
    the same stem in another partition or subdirectory would be a second
    module of the same name.
    """
    groups = {}
    for rel in sorted(files, key=lambda r: (not r.startswith('vendor/'), r.count('/'), r)):
        m = re.fullmatch(r'(\w+)/lib(?:64)?/(?:(.*)/)?([^/]+)\.so', rel)
        if not m:
            continue
        part, sub, stem = m.group(1), m.group(2) or '', m.group(3)
        groups.setdefault(stem, {}).setdefault((part, sub), []).append(rel)
    out = {}
    for stem, by_dir in groups.items():
        first = next(iter(by_dir))
        for (part, sub), rels in by_dir.items():
            if (part, sub) == first:
                continue
            tag = part if part != first[0] else re.sub(r'\W', '_', sub) or 'root'
            for rel in rels:
                out[rel] = f'_{tag}'
    return out


if __name__ == '__main__':
    main()
