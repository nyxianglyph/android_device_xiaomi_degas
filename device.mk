#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#

LOCAL_PATH := device/xiaomi/degas

# The stock vendor (HyperOS, vendor API 34) is taken over as it is, see
# tools/gen-proprietary-files.py. This file only adds what the stock
# vendor does not carry or what the Android build has to produce itself.

# hardware/mediatek's product makefiles read the board's level, before
# BoardConfig.mk is read.
BOARD_SHIPPING_API_LEVEL := 34
PRODUCT_SHIPPING_API_LEVEL := $(BOARD_SHIPPING_API_LEVEL)

# The stock vendor libraries link against VNDK 34.
PRODUCT_EXTRA_VNDK_VERSIONS := 34

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH) \
    hardware/mediatek \
    hardware/mediatek/libion_mtk \
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
    conninfra_loader \
    dmabuf_dump.vendor \
    libion_mtk \
    vendor.mediatek.hardware.lbs@1.0.vendor \
    vendor.mediatek.hardware.mtkpower-V1-ndk.vendor \
    vendor.mediatek.hardware.netdagent@1.0.vendor \
    vendor.nxp.nxpese@1.0.vendor \
    vndservicemanager

# Services built from hardware/mediatek and AOSP in place of the stock ones.
# The audio service hosts the stock audio HAL; Bluetooth audio is the AOSP
# provider with MediaTek's adapter, which hands offloaded sessions to that
# HAL the way its own provider did, and the three interface libraries are
# what the stock audio HAL and power HAL link.
PRODUCT_PACKAGES += \
    android.hardware.audio.service.mediatek \
    android.hardware.bluetooth-service.mediatek \
    android.hardware.bluetooth.audio-impl \
    android.hardware.bluetooth.audio-impl-mediatek-hidl \
    android.hardware.health-service.mediatek \
    android.hardware.memtrack-service.mediatek \
    audio.bluetooth.default \
    vendor.mediatek.hardware.bluetooth.audio-V1-ndk.vendor \
    vendor.mediatek.hardware.bluetooth.audio@2.1.vendor \
    vendor.mediatek.hardware.bluetooth.audio@2.2.vendor \
    wlan_assistant

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

# RenderScript: the stock HAL module opens libRS_internal.so, which it found in
# the VNDK APEX on stock. Here it has to be in /vendor/lib64, with the CPU
# driver it loads in turn; without them every app that blurs an image with
# RenderScript dies.
PRODUCT_PACKAGES += \
    libRS_internal.vendor \
    libRSDriver.vendor

# Touch gestures on a dark screen, the brightness of the always-on display
# and the color scheme
PRODUCT_PACKAGES += \
    DegasParts

# The classic Bluetooth profiles (audio, calls, phone book, messages, files,
# tethering, input). Stock sets them in its product and system partitions,
# which the source build replaces; the LE Audio ones are vendor properties.
PRODUCT_PRODUCT_PROPERTIES += \
    bluetooth.profile.a2dp.source.enabled=true \
    bluetooth.profile.asha.central.enabled=true \
    bluetooth.profile.avrcp.target.enabled=true \
    bluetooth.profile.bas.client.enabled=true \
    bluetooth.profile.gatt.enabled=true \
    bluetooth.profile.hfp.ag.enabled=true \
    bluetooth.profile.hid.device.enabled=true \
    bluetooth.profile.hid.host.enabled=true \
    bluetooth.profile.map.server.enabled=true \
    bluetooth.profile.opp.enabled=true \
    bluetooth.profile.pan.nap.enabled=true \
    bluetooth.profile.pan.panu.enabled=true \
    bluetooth.profile.pbap.server.enabled=true

# Vivid, the color mode the display uses until another one is chosen
PRODUCT_VENDOR_PROPERTIES += \
    persist.sys.sf.native_mode=258

# The touch controller's doze gestures as sensors: a sub-HAL of the stock
# sensor HAL, which loads what hals.conf lists.
PRODUCT_PACKAGES += \
    sensors.degas

PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/configs/sensors/hals.conf:$(TARGET_COPY_OUT_VENDOR)/etc/sensors/hals.conf

# eSIM: OpenEUICC manages the profiles, DegasEsim is the quick settings tile
# that switches the second SIM slot between the card tray and the eSIM chip.
PRODUCT_PACKAGES += \
    DegasEsim \
    OpenEUICC

PRODUCT_COPY_FILES += \
    frameworks/native/data/etc/android.hardware.telephony.euicc.mep.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/permissions/android.hardware.telephony.euicc.mep.xml

# Xiaomi HIDL interface libraries the stock blobs link, built from
# hardware/xiaomi instead of taken from stock (class "interface").
PRODUCT_PACKAGES += \
    vendor.xiaomi.hardware.displayfeature@1.0.vendor \
    vendor.xiaomi.hardware.fx.tunnel@1.0.vendor

PRODUCT_VENDOR_PROPERTIES += \
    persist.vendor.fingerprint.type=udfps_optical \
    persist.vendor.fingerprint.sensor_location=610|2444|105 \
    persist.vendor.fingerprint.udfps.control_illumination=true

# Widevine: the HAL runs from the stock vendor APEX and loads liboemcrypto.so
# from /vendor/lib64, which the APEX only reaches when the vendor partition
# names the library as one it provides. Without this it stays on L3.
PRODUCT_VENDOR_LINKER_CONFIG_FRAGMENTS += \
    $(LOCAL_PATH)/configs/linker.config.json

# Charging control: input_suspend cuts the charger input, there is no bypass.
$(call soong_config_set,lineage_health,charging_control_charging_path,/sys/class/power_supply/battery/input_suspend)
$(call soong_config_set,lineage_health,charging_control_charging_enabled,0)
$(call soong_config_set,lineage_health,charging_control_charging_disabled,1)
$(call soong_config_set_bool,lineage_health,charging_control_supports_bypass,false)

PRODUCT_PACKAGES += \
    vendor.lineage.health-service.default

# Overlays
PRODUCT_PACKAGES += \
    DegasApertureOverlay \
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
