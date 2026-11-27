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
import subprocess
import sys
import xml.etree.ElementTree as ET

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
    # boringssl_self_test64 comes from the source build, with its own rc files.
    r'vendor/etc/(init/)?boringssl_self_test.*\.rc',
    # hardware/mediatek's chipinfo is the stock script and rc, byte for byte.
    r'vendor/etc/init/chipinfo_init\.rc',
    r'vendor/overlay/.*',  # HyperOS RROs; overlay/ holds our own values instead
    # configs/sensors/hals.conf lists the stock sub-HALs and sensors.degas.
    r'vendor/etc/sensors/hals\.conf',
    # Built from hardware/mediatek and AOSP instead, see device.mk: the audio
    # service that hosts the stock audio HAL, the Bluetooth HAL, Bluetooth
    # audio (providers, session libraries, the audio HAL module), the health
    # service, the memtrack service and wlan_assistant. The binaries that share
    # their name with the source module go through stock-shadow-classes.txt.
    # MediaTek's own HIDL providers and their session library stay stock: the
    # stock audio HAL is reached through them for offloaded sessions.
    r'vendor/etc/init/(android\.hardware\.audio\.service\.mediatek|memtrack-mediatek|wlan_assistant)\.rc',
    r'vendor/etc/vintf/manifest/memtrack-mediatek\.xml',
    r'vendor/bin/hw/android\.hardware\.bluetooth-service-mediatek',
    # The older HIDL Bluetooth service, which nothing talks to once the AIDL
    # one is there.
    r'vendor/bin/hw/android\.hardware\.bluetooth@1\.1-service-mediatek',
    r'vendor/etc/init/android\.hardware\.bluetooth@1\.1-service-mediatek\.rc',
    r'vendor/lib(64)?/hw/android\.hardware\.bluetooth@1\.1-impl-mediatek\.so',
    r'vendor/etc/init/android\.hardware\.bluetooth-service-mediatek\.rc',
    r'vendor/etc/vintf/manifest/android\.hardware\.bluetooth-service-mediatek\.xml',
    r'vendor/lib(64)?/android\.hardware\.bluetooth\.audio-impl-mediatek\.so',
    r'vendor/lib(64)?/libbluetooth_audio_session(_aidl|_aidl_mtk)?\.so',
    r'vendor/lib(64)?/hw/audio\.bluetooth\.default\.so',
    r'vendor/lib(64)?/hw/android\.hardware\.bluetooth\.audio@2\.[0-2]-impl\.so',
    r'vendor/etc/vintf/manifest/bluetooth_audio\.xml',
    r'vendor/bin/hw/android\.hardware\.health-service\.example',
    r'vendor/etc/init/android\.hardware\.health-service\.example\.rc',
    r'vendor/etc/vintf/manifest/android\.hardware\.health-service\.example\.xml',
    # The AOSP example CAS service; the source build ships the CAS APEX.
    r'vendor/bin/hw/android\.hardware\.cas-service\.example',
    r'vendor/etc/init/cas-default\.rc',
    r'vendor/etc/vintf/manifest/android\.hardware\.cas-service\.xml',
    # The stock fingerprint service; android.hardware.biometrics.fingerprint-
    # service.xiaomi (hardware/xiaomi) drives the Goodix HAL module instead,
    # with udfps/ doing what the HyperOS framework did on a press. The rc file
    # stays for its permission rules, extract-files.py drops the service.
    r'vendor/bin/hw/mfp-daemon',
    r'vendor/etc/vintf/manifest/(AHBF-V3-service|fod-aidl)\.xml',
    # Fingerprint dump tool of the stock fingerprint service; its interface
    # was declared in fod-aidl.xml.
    r'odm/bin/hw/vendor\.xiaomi\.hardware\.dtool1-service',
    r'odm/etc/init/vendor\.xiaomi\.hardware\.dtool1\.rc',
    # Factory and service tools that write outside the Android partitions:
    # MI_RIC and MI_IC keep memory statistics in the gsort partition, ffu
    # updates the UFS firmware, ddr_training.rc clears boot_para. This ROM
    # never writes there, so they are not shipped at all.
    r'vendor/bin/(MI_RIC|MI_IC|ffu)',
    r'vendor/etc/init/(mi_ric|mi_ic|ffu|ddr_training)\.rc',
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
    # GBA authentication for the supplementary services of IMS (XCAP).
    r'system_ext/priv-app/MtkGbaService/.*',
    r'system_ext/lib64/libimsma.*\.so',
    # JNI library of the ImsService's video call provider; the service loads
    # it at start whether video calls are used or not.
    r'system_ext/lib64/libmtk_vt_wrapper\.so',
    # Dependency closure of libimsma_rtp.
    r'system_ext/lib64/lib(signal|sink|source|comutils|vcodec_cap|vcodec_capenc|vt_avsync)\.so',
    r'system_ext/lib64/vendor\.mediatek\.hardware\.videotelephony.*\.so',
    r'system_ext/etc/sysconfig/com\.mediatek\.ims\.config\.xml',
    r'system_ext/etc/permissions/com\.mediatek\.ims.*\.xml',
]

# Colliding stock files (stock-path-collisions.txt) that are simply left out:
# the shell config of the source build, and the rc of a service that comes
# from the source build.
DROP_ON_COLLISION = re.compile(r'vendor/etc/mkshrc|vendor/etc/init/android\.hardware\.drm-service\.clearkey\.rc')


# Stock files installed under another name.
INSTALL_AS = {
    # hw_get_module_by_class() only finds <id>.<class>.<variant>.so.
    'odm/lib64/hw/fingerprint.goodix_fod.so': 'odm/lib64/hw/fingerprint.goodix_fod.default.so',
    # MediaTek's GNSS library. external/libmnl, a netlink library, is
    # installed to vendor/lib64 under the same file name, where the stock
    # vendor has a link to this one: it goes there as libmnl-v34.so instead
    # and extract-files.py points mnld at it.
    'vendor/lib64/mt6897/libmnl.so': 'vendor/lib64/libmnl-v34.so',
}


# Stock jars device.mk puts on the boot class path. The tag makes
# extract-utils declare them generic, which the system image check demands of
# every boot jar outside /system.
BOOT_JARS = {
    'system_ext/framework/mediatek-ims-base.jar',
    'system_ext/framework/mediatek-ims-common.jar',
    'system_ext/framework/mediatek-telephony-base.jar',
}


def v34_name(rel):
    """<dir>/<stem>-v34<ext>, the installed name of a colliding stock file."""
    base, ext = os.path.splitext(rel)
    return f'{base}-v34{ext}'


# Stock rc files of HIDL services whose interfaces are not built from source:
# the PRODUCT_COPY_FILES check (host_init_verifier) only knows source
# hidl_interfaces, so these are installed as prebuilt_etc packages instead.
PACKAGED_RC = re.compile(r'vendor/etc/init/vendor\.mediatek\.hardware\.aee@1\.1-service\.rc')

# VNDK v34 libraries: on the device they come from the VNDK APEX, and
# extract-files.py leaves them out of the soong deps of the stock blobs.
VNDK_V34 = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../..',
                        'prebuilts/vndk/v34/arm64/configs/module_names.txt')


def elf_dynamic(path):
    """(DT_NEEDED names, DT_SONAME) of an ELF, None for anything else."""
    if not is_elf(path):
        return None
    out = subprocess.run(['readelf', '-d', path], capture_output=True, text=True).stdout
    needed, soname = [], None
    for l in out.splitlines():
        if '(NEEDED)' in l:
            needed.append(l.split('[')[1].split(']')[0])
        elif '(SONAME)' in l:
            soname = l.split('[')[1].split(']')[0]
    return needed, soname


def needs_checkelf_off(rel, full, vndk):
    """True when soong's ELF check cannot pass for a stock blob.

    Either a dependency is a VNDK v34 library (not a soong dep, see above),
    or the stock library carries a SONAME other than its file name.
    """
    info = elf_dynamic(full)
    if info is None:
        return False
    needed, soname = info
    if any(n[:-3] in vndk for n in needed if n.endswith('.so')):
        return True
    return rel.endswith('.so') and soname is not None and soname != os.path.basename(rel)


def not_xml(full):
    # Stock files named *.xml that are not XML (several top-level elements,
    # shell-style comments); the build refuses to copy those as .xml.
    try:
        ET.parse(full)
        return False
    except ET.ParseError:
        return True


def filegroup_name(rel):
    return 'degas_' + re.sub(r'[^\w]', '_', rel)


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
    coll_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                             'stock-path-collisions.txt')
    collisions = set()
    if os.path.exists(coll_path):
        collisions = {l.strip() for l in open(coll_path)
                      if l.strip() and not l.startswith('#')}
    vintf_merged = set()
    for rel in list(files):
        if rel not in collisions:
            continue
        if DROP_ON_COLLISION.fullmatch(rel):
            del files[rel]
            links.pop(rel, None)
        elif '/etc/vintf/' in rel:
            vintf_merged.add(rel)
        elif not rel.endswith('.so') and '/bin/' not in rel:
            renamed[rel] = v34_name(rel)
    for rel in list(files):
        m = re.fullmatch(r'(vendor|odm)/(?:lib(?:64)?/([^/]+)\.so|bin/(?:hw/)?([^/]+))', rel)
        cls = classes.get(m.group(2) or m.group(3)) if m else None
        if cls in ('interface', 'source'):
            del files[rel]
            links.pop(rel, None)
        elif cls == 'v34':
            renamed[rel] = rel[:-3] + '-v34.so'
        elif cls == 'v34bin':
            renamed[rel] = rel + '-v34'

    renamed.update({rel: dst for rel, dst in INSTALL_AS.items() if rel in files})
    for rel, dst in INSTALL_AS.items():
        # The stock links to a file that moves would hang or clash.
        if rel in files and os.path.dirname(rel) != os.path.dirname(dst):
            links.pop(rel, None)

    suffixes = lib_suffixes(files)
    shadowing = set()
    if len(sys.argv) > 2:
        shadowing = {l.strip() for l in open(sys.argv[2]) if l.strip()}
        for rel in files:
            m = re.fullmatch(r'(vendor|odm)/(?:lib(?:64)?/([^/]+)\.so|bin/(?:hw/)?([^/]+))', rel)
            name = m and (m.group(2) or m.group(3))
            if (m and name in shadowing and rel not in suffixes
                    and classes.get(name) not in ('vendor', 'v34', 'v34bin')):
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

    vndk = {l.split()[1] for l in open(VNDK_V34) if l.strip()}
    checkelf_off = {r for r in files if (r.split('/')[1] in ('lib', 'lib64', 'bin')
                                         and needs_checkelf_off(r, os.path.join(dump, r), vndk))}
    # Installed by device/xiaomi/degas/Android.bp from these filegroups.
    not_xml_files = {r for r in files if r.endswith('.xml') and '/etc/' in r
                     and not r.startswith('system_ext/') and '/etc/vintf/' not in r
                     and not_xml(os.path.join(dump, r))}

    section = None
    for rel in sorted(files):
        top = '/'.join(rel.split('/')[:2])
        if top != section:
            section = top
            print(f'\n# {section}')
        args = [f'SYMLINK={l}' for l in sorted(links.get(rel, []))]
        if rel in suffixes:
            args.append(f'MODULE_SUFFIX={suffixes[rel]}')
        if '/etc/vintf/' in rel and (shadows_package(rel, shadowing) or rel in vintf_merged):
            # VINTF files may not be copied either; BoardConfig.mk merges
            # these into the device manifest instead.
            args.append('EXTRACT_ONLY')
        elif is_bin_data(rel, os.path.join(dump, rel)) or (
                shadows_package(rel, shadowing) and rel not in renamed):
            args.append('MAKE_COPY_RULE_ONLY')
        if rel in not_xml_files:
            args += [f'FILEGROUP={filegroup_name(rel)}', 'EXTRACT_ONLY']
        if rel in BOOT_JARS:
            args.append('BOOT_JAR')
        if rel in checkelf_off and rel not in unresolvable32:
            args.append('DISABLE_CHECKELF')
        if rel in unresolvable32:
            # The stock file needs a 32-bit library the stock vendor does not
            # have either; it cannot load there, keep it but drop its deps.
            args.append('DISABLE_DEPS')
        if rel in renamed:
            # Installed as <name>-v34.so next to the source build of <name>;
            # extract-files.py points the stock users at the new name.
            fix = ['FIX_SONAME'] if rel.endswith('.so') else []
            print(';'.join([f'{rel}:{renamed[rel]}'] + args + fix))
            continue
        prefix = '-' if PACKAGED_RC.fullmatch(rel) else ''
        print(prefix + ';'.join([rel] + args))


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
