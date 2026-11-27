#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#

# Like stock, apps run 64-bit only (the Cortex-A715 cores have no AArch32);
# the 32-bit vendor libraries stay for the vendor processes that use them.
# Read by core_64_bit.mk, so it has to come first.
ZYGOTE_FORCE_64 := true

$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/vabc_features.mk)
# First-stage tools: snapuserd for VABC merges in the generic ramdisk
# (init_boot), and linker/e2fsck/fsck.f2fs in the vendor ramdisk, like stock.
$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_ramdisk.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/launch_with_vendor_ramdisk.mk)

# Cross-window blur makes SurfaceFlinger compose with the GPU, which does not
# fit the 144 Hz frame time on this panel (about half the frames were late
# while a blurred surface was on screen).
# Read by vendor/lineage's crdroid.mk, so it has to come before it.
TARGET_SUPPORTS_BLUR := false

# crDroid's camera face unlock, which the ROM no longer ships unless asked.
TARGET_FACE_UNLOCK_SUPPORTED := true

$(call inherit-product, device/xiaomi/degas/device.mk)
$(call inherit-product, vendor/lineage/config/common_full_phone.mk)

PRODUCT_NAME := lineage_degas
PRODUCT_DEVICE := degas
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_BRAND := Xiaomi
PRODUCT_MODEL := 2406APNFAG

PRODUCT_PRODUCT_PROPERTIES += ro.product.marketname=Xiaomi 14T

PRODUCT_SYSTEM_NAME := degas_global
PRODUCT_SYSTEM_DEVICE := degas

PRODUCT_BUILD_PROP_OVERRIDES += \
    BuildDesc="degas_global-user 16 BP2A.250605.031.A3 OS3.0.305.0.WNEMIXM release-keys" \
    DeviceName=$(PRODUCT_SYSTEM_DEVICE) \
    DeviceProduct=$(PRODUCT_SYSTEM_NAME)

BUILD_FINGERPRINT := Xiaomi/degas_global/degas:16/BP2A.250605.031.A3/OS3.0.305.0.WNEMIXM:user/release-keys

# crDroid
TARGET_BOOT_ANIMATION_RES := 1080
TARGET_HAS_UDFPS := true
