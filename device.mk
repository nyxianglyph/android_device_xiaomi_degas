#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := device/xiaomi/degas

# The stock vendor (HyperOS, vendor API 34) is taken over as it is, see
# tools/gen-proprietary-files.py. This file only adds what the stock
# vendor does not carry or what the Android build has to produce itself.

PRODUCT_SHIPPING_API_LEVEL := 34

# The stock vendor libraries link against VNDK 34.
PRODUCT_EXTRA_VNDK_VERSIONS := 34

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH) \
    hardware/mediatek

# Dynamic partitions / Virtual A/B
PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_BUILD_SUPER_PARTITION := false
PRODUCT_VIRTUAL_AB_COMPRESSION_METHOD := lz4

PRODUCT_PACKAGES += \
    checkpoint_gc \
    otapreopt_script \
    update_engine \
    update_engine_sideload \
    update_verifier

AB_OTA_POSTINSTALL_CONFIG += \
    RUN_POSTINSTALL_system=true \
    POSTINSTALL_PATH_system=system/bin/otapreopt_script \
    FILESYSTEM_TYPE_system=erofs \
    POSTINSTALL_OPTIONAL_system=true

# Fastbootd
PRODUCT_PACKAGES += \
    fastbootd

# Partitions built for this device
PRODUCT_BUILD_SYSTEM_DLKM_IMAGE := true
PRODUCT_BUILD_VENDOR_DLKM_IMAGE := true
PRODUCT_BUILD_ODM_DLKM_IMAGE := true

# fstab
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/fstab.mt6897:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.mt6897 \
    $(LOCAL_PATH)/rootdir/etc/fstab.mt6897:$(TARGET_COPY_OUT_VENDOR_RAMDISK)/first_stage_ramdisk/fstab.mt6897

# Display
PRODUCT_AAPT_CONFIG := normal
PRODUCT_AAPT_PREF_CONFIG := xxhdpi

# MediaTek telephony frameworks (AOSP builds, used by the stock ImsService)
$(call inherit-product, hardware/mediatek/frameworks/mediatek-frameworks.mk)

# Proprietary files
$(call inherit-product, vendor/xiaomi/degas/degas-vendor.mk)
