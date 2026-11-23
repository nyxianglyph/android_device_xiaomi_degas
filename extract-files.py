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
import re
import subprocess
import sys

namespace_imports = [
    'device/xiaomi/degas',
    'hardware/mediatek',
    'hardware/xiaomi',
]

here = os.path.dirname(os.path.abspath(__file__))

# How stock files named like a source module are handled (interface, source,
# vendor, v34), see stock-shadow-classes.txt and tools/classify-shadowing.py.
with open(os.path.join(here, 'stock-shadow-classes.txt')) as f:
    shadow_classes = dict(reversed(l.split()) for l in f
                          if l.strip() and not l.startswith('#'))
v34_libs = tuple(sorted(n for n, c in shadow_classes.items() if c == 'v34'))
v34_bins = tuple(sorted(n for n, c in shadow_classes.items() if c == 'v34bin'))

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


# VNDK libraries whose ABI changed without any symbol going missing, so
# tools/check-vendor-deps.py cannot see it: every stock user is pointed at
# the -v34 copy from hardware/lineage/compat. With today's libtinyxml2 the PQ,
# power and miperf services crash while parsing their XML tables.
COMPAT_V34 = ('libtinyxml2',)


def v34_users(dump):
    """Stock vendor/odm ELFs that need a library renamed to <name>-v34.so."""
    names = {f'{n}.so' for n in v34_libs + COMPAT_V34}
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


# Stock blobs that use symbols today's VNDK libraries no longer export (found
# by tools/check-vendor-deps.py), or that share objects with such a blob; they
# link the v34 copies installed by tools/gen-vndk-v34.py instead.
VNDK_V34_USERS = {
    'odm/bin/hw/vendor.xiaomi.sensor.citsensorservice.aidl': ('libui.so',),
    'vendor/bin/hw/wpa_supplicant': ('libcrypto.so', 'libssl.so'),
    'vendor/lib64/hw/mt6897/vendor.mediatek.hardware.pq_aidl-impl.so': ('libui.so',),
    # The Codec2 services: libcodec2_vndk-v34 needs the v34 libui, and every
    # other library of those processes that touches android::GraphicBuffer has
    # to use the same one. With both libui versions loaded the class has two
    # layouts under one symbol name; the decoder then crashed in
    # C2BufferQueueBlockPool::fetchFromIgbp_l() as soon as it decoded to a
    # surface.
    'vendor/lib64/libcodec2_fsr.so': ('libui.so',),
    'vendor/lib64/libcodec2_hidl@1.0-v34.so': ('libstagefright_bufferqueue_helper.so', 'libui.so'),
    'vendor/lib64/libcodec2_hidl@1.1-v34.so': ('libstagefright_bufferqueue_helper.so', 'libui.so'),
    'vendor/lib64/libcodec2_hidl@1.2-v34.so': ('libstagefright_bufferqueue_helper.so', 'libui.so'),
    'vendor/lib64/libcodec2_mtk_vdec.so': ('libui.so',),
    'vendor/lib64/libcodec2_mtk_venc.so': ('libui.so',),
    'vendor/lib64/libcodec2_vndk-v34.so': ('libui.so',),
    'vendor/lib64/libcodec2_vpp_AIMEMC_plugin.so': ('libui.so',),
    'vendor/lib64/libcodec2_vpp_AISR_plugin.so': ('libui.so',),
    'vendor/lib64/libkeymint_remote_prov_support-v34.so': ('libbase.so',),
    'vendor/lib64/libmicamera_hal_core.so': ('libui.so',),
}


# Stock blobs that only miss a few symbols; the hardware/lineage/compat shims
# add them back.
SHIM_USERS = {
    'vendor/bin/pnscr': 'libbase_shim.so',  # android::base::Trim(std::string)
    'vendor/bin/pnscr-sst': 'libbase_shim.so',
    'vendor/lib64/libcameraopt.so': 'libprocessgroup_shim.so',  # SetTaskProfiles
    # android::binder::atrace_begin/atrace_end
    'vendor/lib64/framework-permission-aidl-cpp-v34.so': 'libbinder_shim.so',
}


# Stock AIDL NDK libraries that must not be loaded next to the version the
# framework side uses: every version defines the same symbols, the first one
# loaded wins, and libui then calls IAllocator methods the V1 proxy does not
# have (camerahalserver died in android::waitForAllocator()). Their users are
# linked against the current version instead of the -v34 copy.
AIDL_BUMP = {
    'android.hardware.graphics.allocator-V1-ndk.so':
        'android.hardware.graphics.allocator-V2-ndk.so',
}


def v34_blob_fixups():
    dump = next((a for a in sys.argv[1:] if os.path.isdir(a)), None)
    if dump is None:
        return {}
    renames = {}  # installed path -> libraries to rename to <name>-v34.so
    for hits, rels in v34_users(dump).items():
        for rel in rels:
            renames.setdefault(rel, set()).update(hits)
    for rel, hits in VNDK_V34_USERS.items():
        renames.setdefault(rel, set()).update(hits)
    groups = {}
    for rel in sorted(set(renames) | set(SHIM_USERS)):
        key = (tuple(sorted(renames.get(rel, ()))), SHIM_USERS.get(rel))
        groups.setdefault(key, []).append(rel)
    fixups = {}
    for (hits, shim), rels in groups.items():
        fixup = blob_fixup()
        for name in hits:
            fixup = fixup.replace_needed(name, AIDL_BUMP.get(name, name[:-3] + '-v34.so'))
        if shim:
            fixup = fixup.add_needed(shim)
        fixups[tuple(rels)] = fixup
    return fixups


def renamed_files():
    """(stock path, installed path) of the non-library files renamed to *-v34."""
    with open(os.path.join(here, 'proprietary-files.txt')) as f:
        for line in f:
            spec = line.strip().split(';')[0]
            if ':' in spec and not spec.endswith('.so'):
                yield spec.split(':')


def text_fixups(dump):
    """Point the stock init scripts and XML files at renamed files.

    The binaries of the v34bin class and the colliding config files are
    installed under new names; every stock rc/xml that names them by path or
    basename is patched (the import of init.mt6897.usb.rc, the jar path in
    camera_extensions.xml, the service paths of the renamed HALs).
    """
    subs = []  # (regex, replacement)
    for old, new in renamed_files():
        ob, nb = os.path.basename(old), os.path.basename(new)
        subs.append((r'(?<=[/}])%s(?![\w.@-])' % re.escape(ob), nb))
    dst_of = dict(renamed_files())
    per_file = {}
    for part in ('vendor/etc', 'odm/etc'):
        for root, _, names in os.walk(os.path.join(dump, part)):
            for name in names:
                if not name.endswith(('.rc', '.xml')):
                    continue
                path = os.path.join(root, name)
                rel = os.path.relpath(path, dump)
                with open(path, errors='replace') as f:
                    text = f.read()
                hits = [(p, r) for p, r in subs if re.search(p, text)]
                if hits:
                    per_file[dst_of.get(rel, rel)] = hits
    fixups = {}
    for rel, hits in per_file.items():
        fixup = blob_fixup()
        for p, r in hits:
            fixup = fixup.regex_replace(p, r)
        fixups[rel] = fixup
    return fixups


_dump = next((a for a in sys.argv[1:] if os.path.isdir(a)), None)

blob_fixups: blob_fixups_user_type = {
    **v34_blob_fixups(),
    **(text_fixups(_dump) if _dump else {}),
    # Keep the permission rules of the stock fingerprint rc, but not its
    # service: mfp-daemon is replaced (see tools/gen-proprietary-files.py).
    'vendor/etc/init/init.mfp-daemon.aidl.rc': blob_fixup()
        .regex_replace(r'service mfp-daemon [^\n]*\n(?:[ \t]+[^\n]*\n)+', ''),
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
