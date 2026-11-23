#!/usr/bin/env python3
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
"""Carry the SELinux policy of the stock vendor services over into source form.

The vendor and odm partitions are the stock ones, but their compiled policy
(vendor_sepolicy.cil) is not: the build writes the vendor policy from source.
The source policy this tree builds on (device/mediatek/sepolicy_vndr and the
platform's) knows MediaTek's common services, not Xiaomi's, names some domains
differently, and allows the domains it does have less than the stock blobs
running in them do.

Carried from the stock policy, as .te and *_contexts files of one sepolicy
directory:

- every stock type and attribute the source policy does not have, with its
  rules and labels. A stock type that labels something the source policy
  labels with a type of its own is taken to be that type;
- for the domains both policies have, the stock rules and HAL roles.

Only what can be said in today's policy is carried. A rule that names a type
which no longer exists or is no longer public is left out and counted. Rules
today's neverallow rules reject are listed in sepolicy-stock-exclude.txt: when
the build reports one, add the generated line there and run this again.

What the source policy already has is read from the policy sources, not from
the built policy, which contains the output of earlier runs.

usage: gen-sepolicy.py <dump> <product out> <output dir>
       <dump> holds vendor/etc/selinux and odm/etc/selinux of the stock build,
       <product out> is out/target/product/degas of a build of this tree (for
       the public types of the system side), <output dir> is sepolicy/stock.
"""

import collections
import json
import os
import re
import sys

STOCK_VERS = '34_0'

# Stock domains that exist under another name in the source policy.
RENAME = {
    'mtk_hal_audio': 'hal_audio_default',
    'mtk_hal_audio_exec': 'hal_audio_default_exec',
    'mtk_hal_gnss': 'hal_gnss_default',
    'mtk_hal_gnss_exec': 'hal_gnss_default_exec',
    'mtk_hal_sensors': 'hal_sensors_default',
    'mtk_hal_sensors_exec': 'hal_sensors_default_exec',
    'hal_keymint_strongbox': 'hal_keymint_default',
    'hal_keymint_strongbox_exec': 'hal_keymint_default_exec',
    'st54spi_hal_secure_element': 'hal_secure_element_default',
    'st54spi_hal_secure_element_exec': 'hal_secure_element_default_exec',
}

# Stock types that are not carried: services this tree does not ship (see
# tools/gen-proprietary-files.py) and debug tooling of the stock build.
DROP = re.compile('|'.join([
    r'mi_ric(_.*)?', r'mi_ic(_.*)?', r'ffu(_.*)?', r'ddr_training(_.*)?',
    r'vendor_dtool(_.*)?', r'vendor_mfp-daemon(_.*)?',
]))


# Attributes that say what a type is. For a type the source policy declares
# itself, that is the source policy's call.
SHARED_ATTRS_LEFT_ALONE = {
    'domain', 'coredomain', 'appdomain', 'mlstrustedsubject', 'mlstrustedobject',
    'file_type', 'exec_type', 'vendor_file_type', 'data_file_type', 'core_data_file_type',
    'dev_type', 'fs_type', 'sysfs_type', 'proc_type', 'debugfs_type',
    'property_type', 'vendor_property_type', 'vendor_internal_property_type',
    'vendor_restricted_property_type', 'vendor_public_property_type',
    'system_property_type', 'service_manager_type', 'hwservice_manager_type',
    'vndservice_manager_type', 'protected_service', 'protected_hwservice',
    'vendor_service', 'app_api_service', 'ephemeral_app_api_service',
    'hal_service_type', 'same_process_hwservice', 'coredomain_hwservice',
}


# Platform domains that run the vendor's configuration or load its code. The
# stock vendor policy has rules for them on platform types as well (init
# files that create directories, sysfs nodes the services read); those are
# carried too.
PLATFORM_SOURCES = {
    'init', 'vendor_init', 'ueventd', 'kernel', 'tee', 'vold', 'fsck', 'e2fs',
    'surfaceflinger', 'system_server', 'system_suspend', 'audioserver', 'cameraserver',
    'mediaserver', 'mediaswcodec', 'mediaextractor', 'drmserver', 'bluetooth', 'nfc',
    'radio', 'rild', 'gmscore_app', 'vendor_shell',
}


def sexprs(text):
    """Top-level S-expressions of a CIL file as nested lists."""
    stack = [[]]
    for tok in re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text):
        if tok == '(':
            stack.append([])
        elif tok == ')':
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(tok)
    return stack[0]


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


def context_lines(path):
    """(first field, type, whole line) of a *_contexts file."""
    for line in read(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        fields = line.split()
        label = next((f for f in reversed(fields) if f.startswith('u:object_r:')), None)
        if label is None:
            continue
        yield fields[0], label.split(':')[2], fields


def main():
    dump, product_out, outdir = sys.argv[1:4]
    here = os.path.dirname(os.path.abspath(__file__))

    # --- what this tree's policy already has ---------------------------------
    # Public types of the system side appear in plat_pub_versioned.cil as
    # versioned attributes, attributes as they are. Vendor types are read from
    # the policy sources: the built vendor policy contains the output of an
    # earlier run of this tool.
    ours = set()
    pub = read(os.path.join(product_out, 'vendor/etc/selinux/plat_pub_versioned.cil'))
    cur_vers = read(os.path.join(product_out, 'vendor/etc/selinux/plat_sepolicy_vers.txt')).strip()
    cur_suffix = '_' + cur_vers.replace('.', '_')
    for m in re.finditer(r'^\(typeattribute (\S+)\)', pub, re.M):
        name = m.group(1)
        if name.endswith(cur_suffix):
            ours.add(name[:-len(cur_suffix)])
        elif not name.startswith('base_typeattr_'):
            ours.add(name)

    top = os.path.abspath(os.path.join(product_out, '..', '..', '..', '..'))
    cfg = json.loads(read(os.path.join(top, 'out/soong/soong.lineage_degas.variables')))
    own = os.path.relpath(os.path.abspath(outdir), top)
    vendor_dirs = [d for d in ['system/sepolicy/vendor'] + (cfg.get('BoardVendorSepolicyDirs') or [])
                   if d != own]
    vendor_words = set()
    for d in vendor_dirs:
        for name in sorted(os.listdir(os.path.join(top, d))):
            if not (name.endswith('.te') or name == 'attributes'):
                continue
            # Every name the vendor sources use is declared by them one way
            # or another (type, attribute, a property or domain macro), so
            # any word of theirs counts, comments aside.
            text = re.sub(r'#.*', '', read(os.path.join(top, d, name)))
            if os.path.dirname(d) == os.path.dirname(own):
                # This tree's own rules may name carried types; only what
                # they declare is theirs.
                words = set(re.findall(r'^\s*(?:type|attribute)\s+([A-Za-z0-9_.-]+)',
                                       text, re.M))
            else:
                words = set(re.findall(r'[A-Za-z0-9_.-]+', text))
            ours |= words
            vendor_words |= words
            for hal in re.findall(r'\bhal_attribute\(\s*([A-Za-z0-9_]+)\s*\)', text):
                ours |= {f'hal_{hal}', f'hal_{hal}_client', f'hal_{hal}_server'}
            # app_domain() also declares <domain>_userfaultfd.
            for app in re.findall(r'\bapp_domain\(\s*([A-Za-z0-9_]+)\s*\)', text):
                ours.add(app + '_userfaultfd')

    # Types the system side keeps private: vendor policy can neither use nor
    # redeclare them.
    private = set()
    for part in ('system', 'system_ext', 'product'):
        d = os.path.join(product_out, part, 'etc/selinux')
        for name in os.listdir(d) if os.path.isdir(d) else ():
            if name.endswith('_sepolicy.cil'):
                private |= set(re.findall(r'^\((?:type|typeattribute) (\S+)\)',
                                          read(os.path.join(d, name)), re.M))
    private -= ours
    # Labels the source policy already gives.
    dirs = ['system/sepolicy/private', 'system/sepolicy/public'] + vendor_dirs
    for key in ('SystemExtPrivateSepolicyDirs', 'SystemExtPublicSepolicyDirs',
                'ProductPrivateSepolicyDirs'):
        dirs += cfg.get(key) or []
    our_genfs = set()
    our_labels = collections.defaultdict(dict)   # contexts file name -> key -> type
    kinds = ('file_contexts', 'property_contexts', 'service_contexts',
             'hwservice_contexts', 'vndservice_contexts')
    for d in dirs:
        p = os.path.join(top, d, 'genfs_contexts')
        if os.path.exists(p):
            for line in read(p).split('\n'):
                f = line.split()
                if len(f) >= 4 and f[0] == 'genfscon':
                    our_genfs.add(f'{f[1]} {f[2].strip(chr(34))}')
        for kind in kinds:
            p = os.path.join(top, d, kind)
            if os.path.exists(p):
                for key, typ, _ in context_lines(p):
                    our_labels[kind].setdefault(key, typ)

    def stock_contexts(kind):
        name = kind if kind == 'vndservice_contexts' else 'vendor_' + kind
        for part in ('vendor', 'odm'):
            p = os.path.join(dump, part, 'etc/selinux',
                             name if part == 'vendor' else name.replace('vendor_', 'odm_'))
            if os.path.exists(p):
                yield from context_lines(p)

    # --- the stock policy ----------------------------------------------------
    stock = sexprs(read(os.path.join(dump, 'vendor/etc/selinux/vendor_sepolicy.cil')))
    stock_types = [s[1] for s in stock if s[0] == 'type']
    stock_attrs = [s[1] for s in stock if s[0] == 'typeattribute']
    suffix = '_' + STOCK_VERS

    members = collections.defaultdict(set)   # attribute -> stock member types
    for s in stock:
        if s[0] == 'typeattributeset' and not any(isinstance(m, list) for m in s[2]):
            members[s[1]] |= set(s[2])
    # The domains of Xiaomi's apps and system components: they are not part
    # of this build, and vendor policy may not define core domains.
    stock_apps = members['appdomain'] | members['coredomain']

    # A stock type that labels something the source policy labels with a type
    # of its own is the same thing under another name.
    alias = dict(RENAME)
    for kind in kinds:
        for key, typ, _ in stock_contexts(kind):
            mine = our_labels[kind].get(key)
            if mine and mine != typ and typ not in ours and typ not in alias:
                alias[typ] = mine

    carried = {t for t in stock_types
               if t not in ours and t not in private and t not in alias
               and t not in stock_apps and not DROP.fullmatch(t)}
    carried_attrs = {a for a in stock_attrs
                     if a not in ours and a not in private and not a.endswith(suffix)
                     and not a.startswith('base_typeattr_') and not DROP.fullmatch(a)}
    stock_domains = members['domain']
    # Stock vendor types the source policy has as well, under the same name
    # or another. Their stock rules are carried too: the stock blobs running
    # in those domains do what stock allows, which is more than the generic
    # MediaTek policy knows about.
    shared = {t for t in stock_types if t in vendor_words or t in alias}
    shared |= {t + suffix for t in PLATFORM_SOURCES}
    dropped_names = collections.Counter()

    def tr(name):
        """Name of a stock type or attribute in this tree's policy, or None."""
        if name == 'self':
            return name
        if name in alias:
            return alias[name]
        if name in carried or name in carried_attrs:
            return name
        if name.endswith(suffix):
            base = name[:-len(suffix)]
            if base in ours:
                return base
        elif name in ours:
            return name
        dropped_names[name] += 1
        return None

    compound = {s[1]: s[2] for s in stock
                if s[0] == 'typeattributeset' and s[1].startswith('base_typeattr_')}

    def names(expr):
        """Translated names of a plain list, or None if one is unknown."""
        out = []
        for e in expr:
            if isinstance(e, list):
                return None
            t = tr(e)
            if t is None:
                return None
            out.append(t)
        return out

    def expr_te(expr):
        """A CIL type set expression as a TE one, or None."""
        if isinstance(expr, str):
            if expr in compound:
                return expr_te(compound[expr])
            t = tr(expr)
            return t
        if not expr:
            return None
        if expr[0] == 'and' and len(expr) == 3:
            a, b = expr[1], expr[2]
            if isinstance(b, list) and b and b[0] == 'not':
                pos = names(a if isinstance(a, list) else [a])
                neg = names(b[1] if isinstance(b[1], list) else [b[1]])
                if pos is None or neg is None:
                    return None
                return '{ ' + ' '.join(pos + ['-' + n for n in neg]) + ' }'
            return None
        if expr[0] == 'not' and len(expr) == 2:
            inner = names(expr[1] if isinstance(expr[1], list) else [expr[1]])
            return None if inner is None else '~{ ' + ' '.join(inner) + ' }'
        if expr[0] in ('or', 'all', 'xor'):
            return None
        plain = names(expr)
        return None if plain is None else '{ ' + ' '.join(plain) + ' }'

    def mentions_carried(name):
        if name in carried or name in carried_attrs:
            return True
        if name in compound:
            flat = re.findall(r'[^\s()]+', repr(compound[name]).replace("'", ' ').replace(',', ' '))
            return any(f in carried or f in carried_attrs for f in flat)
        return False

    rules = collections.defaultdict(list)   # owning type -> TE lines
    shared_rules = []
    skipped = collections.Counter()

    def owner(*cands):
        for c in cands:
            if c in carried:
                return c
        for c in cands:
            if c in carried_attrs:
                return c
        return cands[0]

    for s in stock:
        kind = s[0]
        if kind in ('allow', 'dontaudit', 'auditallow'):
            src, tgt, perm = s[1], s[2], s[3]
            new_type = mentions_carried(src) or mentions_carried(tgt)
            if not new_type and not (src in shared or (tgt in shared and tgt in stock_types)):
                continue
            a, b = expr_te(src), expr_te(tgt)
            if a is None or b is None or not isinstance(perm, list) or len(perm) != 2 \
                    or any(isinstance(p, list) for p in perm[1]):
                skipped[kind] += 1
                continue
            if perm[0] == 'binder' and tgt in stock_types and tgt not in stock_domains:
                # Stock has binder rules on service types; they mean nothing
                # and today's neverallow rules reject them.
                skipped['binder on a non-domain'] += 1
                continue
            line = f'{kind} {a} {b}:{perm[0]} {{ {" ".join(perm[1])} }};'
            if new_type:
                rules[owner(src, tgt)].append(line)
            else:
                shared_rules.append(line)
        elif kind == 'allowx':
            src, tgt, x = s[1], s[2], s[3]
            new_type = mentions_carried(src) or mentions_carried(tgt)
            if not new_type and not (src in shared or (tgt in shared and tgt in stock_types)):
                continue
            a, b = expr_te(src), expr_te(tgt)
            if a is None or b is None:
                skipped[kind] += 1
                continue
            cmds = []
            for c in x[2] if isinstance(x[2], list) else [x[2]]:
                cmds.append(f'{c[1]}-{c[2]}' if isinstance(c, list) else c)
            line = f'allowxperm {a} {b}:{x[1]} {x[0]} {{ {" ".join(cmds)} }};'
            if new_type:
                rules[owner(src, tgt)].append(line)
            else:
                shared_rules.append(line)
        elif kind == 'typetransition':
            src, tgt, cls = s[1], s[2], s[3]
            name, new = (s[4], s[5]) if len(s) == 6 else (None, s[4])
            if not (mentions_carried(src) or mentions_carried(tgt) or new in carried):
                continue
            a, b, n = expr_te(src), expr_te(tgt), tr(new)
            if a is None or b is None or n is None:
                skipped[kind] += 1
                continue
            rules[owner(new, src, tgt)].append(
                f'type_transition {a} {b}:{cls} {n}{" " + name if name else ""};')

    # Attributes of the carried types, and stock attributes given to types
    # this tree already has.
    type_attrs = collections.defaultdict(list)
    for s in stock:
        if s[0] != 'typeattributeset' or s[1].startswith('base_typeattr_'):
            continue
        attr = tr(s[1])
        members = s[2]
        if attr is None or any(isinstance(m, list) for m in members):
            continue
        for m in members:
            if m in carried:
                type_attrs[m].append(attr)
            elif s[1] in carried_attrs:
                t = tr(m)
                if t is not None:
                    rules[s[1]].append(f'typeattribute {t} {attr};')
            elif m in shared and m in stock_domains and attr not in SHARED_ATTRS_LEFT_ALONE:
                # HAL client and server roles of domains both policies have.
                shared_rules.append(f'typeattribute {tr(m)} {attr};')

    # Stock rules that today's neverallow rules reject (found by building).
    exclude_file = os.path.join(here, 'sepolicy-stock-exclude.txt')
    exclude = set()
    if os.path.exists(exclude_file):
        exclude = {l.strip() for l in read(exclude_file).split('\n')
                   if l.strip() and not l.startswith('#')}

    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        os.remove(os.path.join(outdir, f))
    head = ('# Generated by tools/gen-sepolicy.py from the stock vendor policy.'
            ' Do not edit.\n')

    with open(os.path.join(outdir, 'attributes'), 'w') as f:
        f.write(head)
        for a in sorted(carried_attrs):
            f.write(f'attribute {a};\n')

    # One .te file per carried domain; everything else by kind.
    def bucket(name):
        if name in carried_attrs:
            return 'attributes_rules'
        for suf in ('_exec', ):
            if name.endswith(suf) and name[:-len(suf)] in carried:
                return name[:-len(suf)]
        if name + '_exec' in carried or 'domain' in type_attrs.get(name, ()):
            return name
        attrs = type_attrs.get(name, ())
        if 'property_type' in attrs:
            return 'property'
        if any(a in attrs for a in ('service_manager_type', 'hwservice_manager_type',
                                    'vndservice_manager_type')):
            return 'service'
        if 'dev_type' in attrs:
            return 'device'
        if 'sysfs_type' in attrs or 'fs_type' in attrs or 'proc_type' in attrs:
            return 'fs'
        return 'file'

    files = collections.defaultdict(lambda: ([], []))
    for t in sorted(carried):
        attrs = sorted(set(type_attrs.get(t, ())))
        files[bucket(t)][0].append(f'type {t}{"".join(", " + a for a in attrs)};')
    for t, lines in rules.items():
        files[bucket(t)][1].extend(lines)
    if shared_rules:
        files['domains_in_both'][1].extend(sorted(set(shared_rules)))
    for name, (decls, lines) in files.items():
        with open(os.path.join(outdir, name + '.te'), 'w') as f:
            f.write(head)
            f.write('\n'.join(decls) + ('\n\n' if decls else ''))
            seen = set(exclude)
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    f.write(line + '\n')

    # Labels. A stock label is carried whenever its type exists here and the
    # source policy does not label the same path; executables also under the
    # name this tree installs them as.
    installed_as = {}
    for line in read(os.path.join(here, '..', 'proprietary-files.txt')).split('\n'):
        spec = line.split(';')[0]
        if ':' in spec:
            src, dst = spec.split(':')
            installed_as['/' + src] = '/' + dst
    fc = []
    for path, typ, fields in stock_contexts('file_contexts'):
        new = tr(typ)
        if new is None:
            continue
        label = fields[-1].replace(f':{typ}:', f':{new}:')
        variants = [path]
        for src, dst in installed_as.items():
            try:
                if re.fullmatch(path, src):
                    variants.append(re.escape(dst).replace('\\/', '/').replace('\\-', '-'))
            except re.error:
                pass
        for v in variants:
            if v not in our_labels['file_contexts']:
                fc.append(' '.join([v] + fields[1:-1] + [label]))
    with open(os.path.join(outdir, 'file_contexts'), 'w') as f:
        f.write(head + '\n'.join(sorted(set(fc))) + '\n')

    genfs = []
    for s in stock:
        if s[0] != 'genfscon':
            continue
        path = s[2].strip('"')
        if s[3][2] in carried and f'{s[1]} {path}' not in our_genfs:
            genfs.append(f'genfscon {s[1]} {path} u:object_r:{s[3][2]}:s0')
    with open(os.path.join(outdir, 'genfs_contexts'), 'w') as f:
        f.write(head + '\n'.join(genfs) + '\n')

    for kind in kinds[1:]:
        lines = []
        for key, typ, fields in stock_contexts(kind):
            new = tr(typ)
            if new is None or key in our_labels[kind]:
                continue
            lines.append(' '.join(f.replace(f':{typ}:', f':{new}:') for f in fields))
        with open(os.path.join(outdir, kind), 'w') as f:
            f.write(head + '\n'.join(sorted(set(lines))) + '\n')

    n_rules = sum(len(set(l)) for _, l in files.values())
    print(f'{len(carried)} types, {len(carried_attrs)} attributes, {n_rules} rules,'
          f' {len(fc)} file labels, {len(genfs)} genfs labels,'
          f' {len(alias) - len(RENAME)} types matched to existing ones by label', file=sys.stderr)
    print(f'left out: {dict(skipped)}', file=sys.stderr)
    print('unknown names: ' + ', '.join(f'{n}({c})' for n, c in dropped_names.most_common(25)),
          file=sys.stderr)


if __name__ == '__main__':
    main()
