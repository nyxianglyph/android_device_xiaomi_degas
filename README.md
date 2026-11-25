Device configuration for Xiaomi 14T
===================================

The Xiaomi 14T (codenamed _"degas"_) is a high-end smartphone from Xiaomi.

It was released in September 2024.

## Device specifications

<table>
<tr>
<td rowspan="12" width="280"><img src="https://i02.appmifile.com/293_operatorx_operatorx_opx/27/09/2024/d714b3e4e95bd2d4817f5d3458b92c45.png" alt="Xiaomi 14T" title="Xiaomi 14T in Titan Blue" width="260"></td>
<th align="right">Basic</th><th align="left">Spec Sheet</th>
</tr>
<tr><td align="right">SoC</td><td>MediaTek Dimensity 8300-Ultra (MT6897, 4 nm)</td></tr>
<tr><td align="right">CPU</td><td>1x3.35 GHz Cortex-A715, 3x3.2 GHz Cortex-A715, 4x2.2 GHz Cortex-A510</td></tr>
<tr><td align="right">GPU</td><td>Mali-G615 MC6</td></tr>
<tr><td align="right">Memory</td><td>12/16 GB RAM (LPDDR5X)</td></tr>
<tr><td align="right">Storage</td><td>256/512 GB (UFS 4.0)</td></tr>
<tr><td align="right">Shipped Android Version</td><td>14, Xiaomi HyperOS</td></tr>
<tr><td align="right">Battery</td><td>Non-removable 5000 mAh, 67 W wired charging</td></tr>
<tr><td align="right">Display</td><td>AMOLED, 6.67 inches, 1220 x 2712 pixels (446 ppi), 144 Hz</td></tr>
<tr><td align="right">Rear camera</td><td>50 MP wide (OIS), 50 MP telephoto (2x), 12 MP ultra wide-angle</td></tr>
<tr><td align="right">Front camera</td><td>32 MP</td></tr>
<tr><td align="right">Fingerprint</td><td>Under-display, optical</td></tr>
</table>

## About this tree

crDroid 16.0 (Android 16). Written from scratch; the vendor and odm partitions
are rebuilt from the stock HyperOS Global `OS3.0.305.0.WNEMIXM` files, the
kernel is
[android_kernel_xiaomi_degas](https://github.com/nyxianglyph/android_kernel_xiaomi_degas/tree/android-6.1.157),
branch `android-6.1.157` (GKI 6.1.157 with KernelSU), shipped as a prebuilt.

Maintainer: nyxianglyph.

## Status

Beta. Used daily on one phone.

Works:

- Calls, mobile data (LTE/5G), VoLTE
- Wi-Fi, hotspot, USB tethering
- Bluetooth, NFC, GPS
- Display at 144 Hz, brightness, auto-brightness
- Under-display fingerprint: enroll, unlock and app prompts
- Cameras, in the ROM's camera app (not tested in depth)
- Call and media audio, video playback (hardware decoders)
- Vibration, with the stock haptic effects
- Encryption, screen lock
- SELinux enforcing
- KernelSU (use the official manager)
- Google apps, in the build made with them: Play Store works, Play Integrity
  passes

Not there yet:

- VoWiFi and video calls over LTE are not set up
- Background blur is off: it does not fit the 144 Hz frame time on this panel
- No OTA updates yet; install is by fastboot

## Building

```sh
repo init -u https://github.com/crdroidandroid/android.git -b 16.0 --git-lfs
```

Add to `.repo/local_manifests/degas.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <project path="device/xiaomi/degas" name="nyxianglyph/android_device_xiaomi_degas" remote="github" revision="16.0" />
  <project path="device/xiaomi/degas-kernel" name="nyxianglyph/android_device_xiaomi_degas-kernel" remote="github" revision="16.0" />
  <project path="hardware/mediatek" name="LineageOS/android_hardware_mediatek" remote="github" revision="lineage-23.2" />
  <project path="hardware/xiaomi" name="LineageOS/android_hardware_xiaomi" remote="github" revision="lineage-23.2" />
  <project path="device/mediatek/sepolicy_vndr" name="LineageOS/android_device_mediatek_sepolicy_vndr" remote="github" revision="lineage-23.2" />
</manifest>
```

```sh
repo sync
```

Five changes to the ROM source come with the tree, in `patches/`:

- two let a device choose the refresh rate for the fingerprint sensor and hold
  the display at it for as long as the sensor area is on screen; without them
  the whole screen brightens when a finger is pressed on the sensor;
- one gives SystemUI the doze options this panel needs; without it the
  always-on display turns black a few seconds after the screen is locked;
- one names a network from the carrier list when the modem reports only its
  number; without it some networks show as a number such as 28602;
- one lets Aperture take the main cameras from an overlay and record 60 fps
  video; without it the camera app offers one lens and 30 fps.

```sh
for dir in frameworks_base frameworks_opt_telephony packages_apps_Aperture; do
    git -C "$(echo $dir | tr _ /)" am "$PWD"/device/xiaomi/degas/patches/$dir/*.patch
done
```

The stock files are not in a repository. Unpack `super.img` of the stock
HyperOS Global `OS3.0.305.0.WNEMIXM` fastboot package into a directory that
holds `vendor/`, `odm/` and `system_ext/` as they are on the phone, then:

```sh
cd device/xiaomi/degas
./extract-files.py /path/to/that/directory
cd ../../..
. build/envsetup.sh
lunch lineage_degas-bp4a-userdebug
m bootimage initbootimage vendorbootimage systemimage systemextimage productimage \
  vendorimage odmimage vbmetaimage vbmetasystemimage vbmetavendorimage
```

### With Google apps

The system partitions are read-only EROFS images, so Google apps cannot be
flashed afterwards; they are built in. The tree takes
[MindTheGapps](https://gitlab.com/MindTheGapps/vendor_gapps) from
`vendor/gapps` when the build is started with `WITH_GMS=true`. Its two
largest apps are stored with Git LFS, so `git-lfs` has to be installed before
cloning:

```sh
git clone -b baklava https://gitlab.com/MindTheGapps/vendor_gapps.git vendor/gapps
git -C vendor/gapps am "$PWD"/device/xiaomi/degas/patches/vendor_gapps/*.patch
m installclean
WITH_GMS=true m bootimage initbootimage ...
```

The patch takes two files out of MindTheGapps that a crDroid build already
has (the keyboard's gesture library and `sysconfig/google.xml`).
`m installclean` is needed whenever the build changes between the two
variants.

## How the tree is put together

- `proprietary-files.txt` is generated by `tools/gen-proprietary-files.py` from
  the stock dump: the stock vendor and odm are taken over whole, minus what the
  build makes itself. `props/*.prop` come from the stock build.prop files through
  `tools/gen-props.py`.
- Stock blobs were built against the Android 14 VNDK. They run on the vendor
  variants of today's libraries where they can; the rest link `-v34` copies
  (`tools/gen-vndk-v34.py`, `hardware/lineage/compat`). `tools/check-vendor-deps.py`
  checks every blob's dependencies and symbols on the host.
- `sepolicy/stock` is generated by `tools/gen-sepolicy.py` from the stock vendor
  policy: the types, rules and labels of the stock services that the source
  policy (device/mediatek/sepolicy_vndr) does not have. `sepolicy/vendor` and
  `sepolicy/private` hold what this tree adds.
- `udfps/` lights the fingerprint sensor area and tells the Goodix HAL about a
  press. The panel does that cleanly at 120 Hz only, so the overlays hold the
  display at 120 Hz wherever the sensor area is shown; `ims/` holds what the
  stock MediaTek IMS service needs on an AOSP framework; `rootdir/` the init
  files, including GPU frequency scaling and the thermal scenario.
- The bootloader of this phone only boots a kernel compressed with legacy LZ4,
  an `init_boot` with a version 4 header and the MediaTek-signed stock `dtbo`
  (`prebuilt/dtbo.img`). `BoardConfig.mk` has the details.

## Installing

Release archives contain the images and `flash-degas.sh`. The script erases
the phone and writes the Android partitions of the active slot from fastboot.
It needs an unlocked bootloader and the stock firmware named above.
