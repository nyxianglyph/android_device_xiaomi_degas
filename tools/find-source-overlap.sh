#!/bin/bash
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
# List the stock vendor/odm shared libraries whose names are also modules in
# the source tree, including the <interface>-V<n>-{ndk,cpp} libraries that
# aidl_interface modules generate. They are kept as the stock binaries under
# a _vendor module name (see extract-files.py), so the vendor runs on what
# HyperOS shipped.
#
# usage: tools/find-source-overlap.sh > stock-libs-shadowing-source.txt
#        (from the device tree, with the Android tree at ../../..)
set -euo pipefail
export LC_ALL=C
cd "$(dirname "$0")/.."
top=../../..
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

grep -vE '^#|^$' proprietary-files.txt | cut -d';' -f1 \
  | grep -E '^(vendor|odm)/(lib(64)?/[^/]+\.so|bin/(hw/)?[^/]+)$' | sed -E 's|.*/||; s/\.so$//' | sort -u > "$tmp/stock"
(cd $top && find . \( -path ./out -o -path ./vendor/xiaomi -o -path ./.repo -o -path ./prebuilts \) -prune \
    -o -name Android.bp -print | xargs grep -hoE '^\s*name:\s*"[^"]+"' \
    | sed -E 's/.*"([^"]+)"/\1/' | sort -u) > "$tmp/source"

# Package-type files (VINTF fragments by file name, jars/apks/apexes by stem).
grep -vE '^#|^$' proprietary-files.txt | cut -d';' -f1 \
  | grep -E '^(vendor|odm|system_ext)/(etc/vintf/.*|.*\.(apk|jar|apex))$' \
  | sed -E 's|.*/||; s/\.(apk|jar|apex)$//' | sort -u > "$tmp/packages"

{
  comm -12 "$tmp/stock" "$tmp/source"
  comm -12 "$tmp/packages" "$tmp/source"
  # Generated AIDL backends: shadowing if the interface itself is a module.
  sed -nE -e '/-V[0-9]+-(ndk|cpp|ndk_platform)$/{s/^(.+)-V[0-9]+-(ndk|cpp|ndk_platform)$/\1 &/p;d}' \
      -e 's/^(.+)-(ndk|cpp|ndk_platform)$/\1 &/p' "$tmp/stock" | sort -k1,1 \
    | join - "$tmp/source" | cut -d' ' -f2
} | sort -u
