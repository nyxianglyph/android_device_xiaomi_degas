#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/degas
KERNEL_PATH := device/xiaomi/degas-kernel

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-2a-dotprod
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := generic
TARGET_CPU_VARIANT_RUNTIME := cortex-a715

TARGET_2ND_ARCH := arm
TARGET_2ND_ARCH_VARIANT := armv8-2a
TARGET_2ND_CPU_ABI := armeabi-v7a
TARGET_2ND_CPU_ABI2 := armeabi
TARGET_2ND_CPU_VARIANT := generic
TARGET_2ND_CPU_VARIANT_RUNTIME := cortex-a520

# Platform
TARGET_BOARD_PLATFORM := mt6897
TARGET_BOOTLOADER_BOARD_NAME := degas
TARGET_NO_BOOTLOADER := true
BOARD_HAS_MTK_HARDWARE := true

# A/B
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    boot \
    dtbo \
    init_boot \
    odm \
    odm_dlkm \
    product \
    system \
    system_dlkm \
    system_ext \
    vbmeta \
    vbmeta_system \
    vbmeta_vendor \
    vendor \
    vendor_boot \
    vendor_dlkm

# Boot image (header v4: kernel in boot, ramdisk in init_boot, vendor ramdisk in vendor_boot)
BOARD_BOOT_HEADER_VERSION := 4
BOARD_KERNEL_PAGESIZE := 4096
BOARD_KERNEL_BASE := 0x3fff8000
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x26f08000
BOARD_KERNEL_TAGS_OFFSET := 0x07c88000
BOARD_DTB_OFFSET := 0x07c88000
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS += --pagesize $(BOARD_KERNEL_PAGESIZE)
BOARD_MKBOOTIMG_ARGS += --base $(BOARD_KERNEL_BASE)
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_KERNEL_TAGS_OFFSET)
BOARD_MKBOOTIMG_ARGS += --dtb_offset $(BOARD_DTB_OFFSET)
BOARD_KERNEL_CMDLINE := bootopt=64S3,32N2,64N2
# Bring-up only: collect denials with SELinux permissive, then remove this.
BOARD_BOOTCONFIG := androidboot.selinux=permissive

BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_RAMDISK_USE_LZ4 := true
BOARD_USES_GENERIC_KERNEL_IMAGE := true
BOARD_MOVE_GSI_AVB_KEYS_TO_VENDOR_BOOT := true
BOARD_MOVE_RECOVERY_RESOURCES_TO_VENDOR_BOOT := true
BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT := true

# Kernel (prebuilt from github.com/nyxianglyph/android_kernel_xiaomi_degas, branch android-6.1.157)
TARGET_PREBUILT_KERNEL := $(KERNEL_PATH)/Image
BOARD_PREBUILT_DTBIMAGE_DIR := $(KERNEL_PATH)/dtb
BOARD_PREBUILT_DTBOIMAGE := $(KERNEL_PATH)/dtbo.img
BOARD_KERNEL_IMAGE_NAME := Image

# Kernel modules: vendor_boot and vendor_dlkm are the stock vendor modules, system_dlkm
# are the GKI modules of the same kernel build (signed with its key).
BOARD_VENDOR_RAMDISK_KERNEL_MODULES := $(wildcard $(KERNEL_PATH)/modules/vendor_boot/*.ko)
BOARD_VENDOR_RAMDISK_KERNEL_MODULES_LOAD := $(strip $(shell cat $(DEVICE_PATH)/modules/vendor_boot.modules.load))
BOARD_VENDOR_RAMDISK_RECOVERY_KERNEL_MODULES_LOAD := $(strip $(shell cat $(DEVICE_PATH)/modules/vendor_boot.modules.load.recovery))
BOARD_VENDOR_KERNEL_MODULES := $(wildcard $(KERNEL_PATH)/modules/vendor_dlkm/*.ko)
BOARD_VENDOR_KERNEL_MODULES_LOAD := $(strip $(shell cat $(DEVICE_PATH)/modules/vendor_dlkm.modules.load))
BOARD_SYSTEM_KERNEL_MODULES := $(wildcard $(KERNEL_PATH)/modules/system_dlkm/*.ko)
BOARD_SYSTEM_KERNEL_MODULES_LOAD := $(strip $(shell cat $(DEVICE_PATH)/modules/system_dlkm.modules.load))

# Partitions
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE := 8388608
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_DTBOIMG_PARTITION_SIZE := 8388608

BOARD_SUPER_PARTITION_SIZE := 9663676416
BOARD_SUPER_PARTITION_GROUPS := xiaomi_dynamic_partitions
BOARD_XIAOMI_DYNAMIC_PARTITIONS_SIZE := 9653190656
BOARD_XIAOMI_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    odm \
    odm_dlkm \
    product \
    system \
    system_dlkm \
    system_ext \
    vendor \
    vendor_dlkm

$(foreach p, $(call to-upper, $(BOARD_XIAOMI_DYNAMIC_PARTITIONS_PARTITION_LIST)), \
    $(eval BOARD_$(p)IMAGE_FILE_SYSTEM_TYPE := erofs) \
    $(eval TARGET_COPY_OUT_$(p) := $(call to-lower, $(p))))

BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs
BOARD_EROFS_PCLUSTER_SIZE := 262144
TARGET_USERIMAGES_USE_F2FS := true
TARGET_USERIMAGES_USE_EXT4 := true

# Virtual A/B
BOARD_USES_METADATA_PARTITION := true

# Recovery
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/rootdir/etc/fstab.mt6897
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888
TARGET_RECOVERY_UI_MARGIN_HEIGHT := 102

# Display
TARGET_SCREEN_DENSITY := 480

# Verified boot
BOARD_AVB_ENABLE := true
BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS += --flags 3
BOARD_AVB_VBMETA_SYSTEM := product system system_ext
BOARD_AVB_VBMETA_SYSTEM_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VBMETA_SYSTEM_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION := 2
BOARD_AVB_VBMETA_VENDOR := odm vendor
BOARD_AVB_VBMETA_VENDOR_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VBMETA_VENDOR_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VBMETA_VENDOR_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_VENDOR_ROLLBACK_INDEX_LOCATION := 3

# The boot images carry the stock HyperOS AVB props, otherwise MiTEE KeyMint
# rejects the metadata encryption key.
BOARD_AVB_BOOT_ADD_HASH_FOOTER_ARGS += \
    --prop com.android.build.boot.os_version:14 \
    --prop com.android.build.boot.security_patch:2026-09-01 \
    --prop com.android.build.boot.fingerprint:Xiaomi/hal_mgvi_64_armv82_mt6897_global/mgvi_64_armv82:14/UP1A.231005.007/OS3.0.305.0.WNEMIXM:user/release-keys
BOARD_AVB_INIT_BOOT_ADD_HASH_FOOTER_ARGS += \
    --prop com.android.build.init_boot.os_version:14 \
    --prop com.android.build.init_boot.security_patch:2026-09-01 \
    --prop com.android.build.init_boot.fingerprint:Xiaomi/hal_mgvi_64_armv82_mt6897_global/mgvi_64_armv82:14/UP1A.231005.007/OS3.0.305.0.WNEMIXM:user/release-keys

BOARD_AVB_VENDOR_BOOT_ADD_HASH_FOOTER_ARGS += \
    --prop com.android.build.vendor_boot.fingerprint:Xiaomi/hal_mgvi_64_armv82_mt6897_global/mgvi_64_armv82:14/UP1A.231005.007/OS3.0.305.0.WNEMIXM:user/release-keys

# VINTF
DEVICE_MANIFEST_FILE += $(DEVICE_PATH)/vintf/manifest.xml
# Stock VINTF fragments named like a source module cannot be packaged or
# copied (see tools/gen-proprietary-files.py); merge them into the manifest.
DEVICE_MANIFEST_FILE += $(addprefix vendor/xiaomi/degas/proprietary/, \
    $(shell sed -n 's|^\(vendor/etc/vintf/[^;]*\);EXTRACT_ONLY$$|\1|p' $(DEVICE_PATH)/proprietary-files.txt))
DEVICE_MATRIX_FILE := $(DEVICE_PATH)/vintf/compatibility_matrix.xml

# Properties
TARGET_VENDOR_PROP += $(DEVICE_PATH)/props/vendor.prop
TARGET_ODM_PROP += $(DEVICE_PATH)/props/odm.prop

# SELinux
include device/mediatek/sepolicy_vndr/SEPolicy.mk
BOARD_VENDOR_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor
SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/private

# VNDK / vendor API
BOARD_SHIPPING_API_LEVEL := 34

# Proprietary
include vendor/xiaomi/degas/BoardConfigVendor.mk

# Init: opcust carrier props and RSC props (see init/init_degas.cpp)
$(call soong_config_set,libinit,vendor_init_lib,//$(DEVICE_PATH):libinit_degas)

# Mount point of the factory opcust partition (see rootdir/etc/fstab.mt6897)
BOARD_ROOT_EXTRA_FOLDERS := opcust
