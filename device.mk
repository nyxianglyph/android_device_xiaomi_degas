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
    hardware/mediatek \
    hardware/xiaomi

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

# Recovery needs a boot control service of its own to install an update
# package and switch slots; the running system uses the stock one.
PRODUCT_PACKAGES += \
    android.hardware.boot-service.mediatek_recovery

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
    $(LOCAL_PATH)/rootdir/etc/fstab.mt6897:$(TARGET_COPY_OUT_VENDOR_RAMDISK)/first_stage_ramdisk/fstab.mt6897 \
    $(LOCAL_PATH)/rootdir/etc/fstab.enableswap:$(TARGET_COPY_OUT_VENDOR)/etc/fstab.enableswap

# Source modules standing in for stock vendor files that extract-files leaves
# out (see tools/gen-proprietary-files.py EXCLUDE and stock-shadow-classes.txt).
# AOSP adds vndservicemanager only for shipping API <= 29, but the stock vendor
# HALs register with vndbinder.
PRODUCT_PACKAGES += \
    android.hardware.drm-service.clearkey \
    chipinfo \
    dmabuf_dump.vendor \
    vendor.nxp.nxpese@1.0.vendor \
    vndservicemanager

# VNDK v34 libraries the stock vendor and odm blobs link against. HyperOS loads
# them from the com.android.vndk.v34 APEX, but this vendor mixes in modules
# built from source and cannot run in VNDK mode (ro.vndk.version unset), so
# install their vendor variants instead. Regenerate the list with
# tools/check-vendor-deps.py.
PRODUCT_PACKAGES += \
    android.frameworks.cameraservice.common-V1-ndk.vendor \
    android.frameworks.cameraservice.device-V1-ndk.vendor \
    android.frameworks.cameraservice.service-V1-ndk.vendor \
    android.frameworks.sensorservice@1.0.vendor \
    android.hardware.common.fmq-V1-ndk.vendor \
    android.hardware.graphics.allocator@2.0.vendor \
    android.hardware.graphics.allocator@3.0.vendor \
    android.hardware.graphics.allocator@4.0.vendor \
    android.hardware.graphics.allocator-V2-ndk.vendor \
    android.hardware.graphics.common-V4-ndk.vendor \
    android.hardware.graphics.mapper@2.0.vendor \
    android.hardware.graphics.mapper@2.1.vendor \
    android.hardware.graphics.mapper@3.0.vendor \
    android.hardware.graphics.mapper@4.0.vendor \
    android.hardware.memtrack-V1-ndk.vendor \
    android.hardware.renderscript@1.0.vendor \
    android.hardware.secure_element@1.0.vendor \
    android.hardware.secure_element@1.2.vendor \
    android.hidl.allocator@1.0.vendor \
    android.system.suspend@1.0.vendor \
    libaudioutils.vendor \
    libbinder.vendor \
    libcamera_metadata.vendor \
    libcodec2.vendor \
    libcurl.vendor \
    libdmabufheap.vendor \
    libdumpstateutil.vendor \
    libevent.vendor \
    libexif.vendor \
    libexpat.vendor \
    libfmq.vendor \
    libgatekeeper.vendor \
    libgralloctypes.vendor \
    libhardware.vendor \
    libhardware_legacy.vendor \
    libhidlmemory.vendor \
    libion.vendor \
    libjpeg.vendor \
    libjsoncpp.vendor \
    liblz4.vendor \
    liblzma.vendor \
    libmedia_helper.vendor \
    libminijail.vendor \
    libnetutils.vendor \
    libnl.vendor \
    libpiex.vendor \
    libpng.vendor \
    libpower.vendor \
    libprocessgroup.vendor \
    libsqlite.vendor \
    libssl.vendor \
    libstagefright_bufferqueue_helper.vendor \
    libstagefright_foundation.vendor \
    libsysutils.vendor \
    libtinyalsa.vendor \
    libtinyxml2.vendor \
    libui.vendor \
    libunwindstack.vendor \
    libutilscallstack.vendor \
    libwifi-system-iface.vendor \
    libxml2.vendor \
    libyuv.vendor \
    libziparchive.vendor \
    vendor.mediatek.hardware.mtkpower@1.0.vendor

# VNDK v34 libraries some blobs need by their old ABI (tools/gen-vndk-v34.py
# and hardware/lineage/compat), and the compat shims that add back symbols
# today's libraries dropped.
PRODUCT_PACKAGES += \
    libbase-v34 \
    libcrypto-v34 \
    libssl-v34 \
    libstagefright_bufferqueue_helper-v34 \
    libtinyxml2-v34 \
    libui-v34 \
    libbase_shim \
    libbinder_shim.vendor \
    libprocessgroup_shim

# Permissions
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/configs/permissions/privapp-permissions-com.mediatek.ims.xml:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/permissions/privapp-permissions-com.mediatek.ims.xml

# Fingerprint: the hardware/xiaomi service drives the stock Goodix optical
# HAL module (odm/lib64/hw/fingerprint.goodix_fod.default.so, V2 device
# struct); udfps/ lights the sensor area and tells the touch controller and
# the HAL about a press. The sensor is centered at (610, 2444), 105 px radius
# (persist.vendor.sys.fp.fod.location.X_Y and .size.width_height on stock).
$(call soong_config_set,XIAOMI_BIOMETRICS_FINGERPRINT,IMPL_VER,V2)

PRODUCT_PACKAGES += \
    android.hardware.biometrics.fingerprint-service.xiaomi \
    libudfpshandler

# Xiaomi HIDL interface libraries the stock blobs link, built from
# hardware/xiaomi instead of taken from stock (class "interface").
PRODUCT_PACKAGES += \
    vendor.xiaomi.hardware.displayfeature@1.0.vendor \
    vendor.xiaomi.hardware.fx.tunnel@1.0.vendor

PRODUCT_VENDOR_PROPERTIES += \
    persist.vendor.fingerprint.type=udfps_optical \
    persist.vendor.fingerprint.sensor_location=610|2444|105 \
    persist.vendor.fingerprint.udfps.control_illumination=true

# Overlays
PRODUCT_PACKAGES += \
    DegasCarrierConfigOverlay \
    DegasFrameworksOverlay \
    DegasSecureElementOverlay \
    DegasSettingsOverlay \
    DegasSystemUIOverlay

# Device nodes
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/ueventd.degas.rc:$(TARGET_COPY_OUT_ODM)/etc/ueventd.rc

# Init
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/init.degas.rc:$(TARGET_COPY_OUT_VENDOR)/etc/init/init.degas.rc \
    $(LOCAL_PATH)/rootdir/bin/thermal-scenario.sh:$(TARGET_COPY_OUT_VENDOR)/bin/thermal-scenario.sh

# Vendor libraries that log every sensor sample or frame at info level.
PRODUCT_VENDOR_PROPERTIES += \
    log.tag.libsensor-displayalgo=W \
    log.tag.libsensor-frameBufferManager=W \
    log.tag.libsensor-parseRGB=W \
    log.tag.libcomposer_ext=I

# Recovery
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/rootdir/etc/init.recovery.mt6897.rc:$(TARGET_COPY_OUT_RECOVERY)/root/init.recovery.mt6897.rc

# Development aids (early adb, boot logs), kept outside git; see
# bringup/bringup.mk where it exists.
ifeq ($(DEGAS_BRINGUP),true)
-include $(LOCAL_PATH)/bringup/bringup.mk
endif

# Display
PRODUCT_AAPT_CONFIG := normal
PRODUCT_AAPT_PREF_CONFIG := xxhdpi

# MediaTek telephony frameworks (AOSP builds, used by the stock ImsService)
$(call inherit-product, hardware/mediatek/frameworks/mediatek-frameworks.mk)
# Classes the stock MediaTek ImsService still links but AOSP dropped
# (com.android.internal.telephony.metrics.TelephonyMetrics), as a boot jar.
$(call inherit-product, hardware/lineage/compat/frameworks/compat.mk)

# IMS (VoLTE). The stock ImsService extends classes of the stock MediaTek IMS
# and telephony-base jars, so those have to be on the boot class path (the
# BOOT_JAR tag in proprietary-files.txt puts them there); with
# hardware/mediatek's small telephony-common and the one stub class below,
# every class and member the service uses resolves.
PRODUCT_PACKAGES += \
    degas-telephony-stub \
    MtkProtectedBroadcasts

# The stock JNI library of the ImsService (libmtk_vt_wrapper) still lists
# libhidltransport, which is an empty library today and installed nowhere
# unless asked for.
PRODUCT_PACKAGES += \
    libhidltransport

PRODUCT_BOOT_JARS += \
    system_ext:degas-telephony-stub

# MediaTek's framework and telephony configuration (com.mediatek.ims as the
# IMS package, VoLTE as a device capability, Wi-Fi capabilities of the
# chipset). The vendor RIL is the stock one.
ENABLE_VENDOR_RIL_SERVICE := true
$(call inherit-product, hardware/mediatek/overlay/mssi.mk)

# Stock camera feature tables, see Android.bp
PRODUCT_PACKAGES += \
    gma_custom.xml_mt6897 \
    gma_custom.xml_mt6985 \
    gma_custom.xml_mt6989

# Proprietary files
$(call inherit-product, vendor/xiaomi/degas/degas-vendor.mk)

# Google apps, for a build with WITH_GMS=true: MindTheGapps in vendor/gapps
# (https://gitlab.com/MindTheGapps/vendor_gapps, branch baklava).
ifeq ($(WITH_GMS),true)
$(call inherit-product, vendor/gapps/arm64/arm64-vendor.mk)
endif
