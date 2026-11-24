#!/vendor/bin/sh
#
# Copyright (C) 2026 nyxianglyph
#
# SPDX-License-Identifier: Apache-2.0
#
# Thermal scenario for Xiaomi's mi_thermald.
#
# mi_thermald throttles by the scenario in thermal_message/sconfig, which the
# HyperOS framework sets from the app in the foreground. Nothing sets it on
# AOSP, and the daemon then stays in its default profile, which already limits
# the CPUs to 2.0/2.66/2.8 GHz and the GPU to 601 MHz at a board temperature
# of 37 C - a phone that is merely in use.
#
# While the board is cool this selects the "nolimits" scenario (6), which
# keeps mi_thermald's own last-resort limits; once the board reaches WARM the
# default profile takes over until it has cooled down to COOL again.
#
# The default profile is felt at once: SurfaceFlinger needs about twice as
# long to compose a frame with the GPU held back (6 ms against 3.3 ms, with a
# 6.9 ms frame at 144 Hz), and window transitions then lose a quarter of
# their frames instead of a tenth. A phone that is charging and in use
# crosses 43 C easily, so the limits start at 46 C.
#
# mi_thermald only reacts to a change of sconfig, so this is started after
# boot has completed, when the daemon is watching the file.

TM=/sys/class/thermal/thermal_message
SCONFIG_DEFAULT=-1
SCONFIG_NOLIMITS=6
WARM=46000
COOL=43000

mode=
while :; do
    t=$(cat $TM/board_sensor_temp 2>/dev/null)
    case "$t" in
    -*) t=0 ;;
    esac
    case "$t" in
    '' | *[!0-9]*) ;;
    *)
        if [ "$mode" != nolimits ] && [ "$t" -le $COOL ]; then
            echo $SCONFIG_NOLIMITS > $TM/sconfig && mode=nolimits
        elif [ "$mode" != default ] && [ "$t" -ge $WARM ]; then
            echo $SCONFIG_DEFAULT > $TM/sconfig && mode=default
        fi
        ;;
    esac
    sleep 5
done
