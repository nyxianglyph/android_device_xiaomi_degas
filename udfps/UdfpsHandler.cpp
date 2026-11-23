/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "UdfpsHandler.degas"

#include <aidl/android/hardware/biometrics/fingerprint/AcquiredInfo.h>
#include <android-base/logging.h>
#include <android-base/unique_fd.h>

#include <fcntl.h>
#include <sys/ioctl.h>

#include <chrono>
#include <condition_variable>
#include <mutex>
#include <optional>
#include <thread>

#include "UdfpsHandler.h"
#include "mi_abi.h"

using ::aidl::android::hardware::biometrics::fingerprint::AcquiredInfo;
using std::chrono::milliseconds;
using std::chrono::steady_clock;

namespace {

constexpr char kTouchDev[] = "/dev/xiaomi-touch";
constexpr char kDispFeatureDev[] = "/dev/mi_display/disp_feature";

// extCmd() requests of the Goodix optical HAL.
constexpr int32_t kCmdFodPressStatus = 1;
constexpr int32_t kCmdNit = 10;
constexpr int32_t kNitOff = 0;
constexpr int32_t kNit1000 = 1;

// The panel does not report when the local HBM spot is lit on this device, so
// the sensor is told after a fixed delay.
constexpr milliseconds kLhbmSettle{80};
// A press that never sees a finger-up (the overlay can go away first) must not
// leave the spot lit.
constexpr milliseconds kPressTimeout{1000};
// The off request is repeated once, in case a late HAL request relit the spot.
constexpr milliseconds kOffRepeat{150};

/*
 * Optical UDFPS on the Xiaomi 14T. A press needs three things the AOSP
 * framework does not do: the panel has to light the sensor area (local HBM),
 * the touch controller has to be put in FOD mode, and the Goodix HAL has to be
 * told about the press and about the light being ready.
 *
 * Every hardware request is made by one worker thread, which also owns the
 * timers, so a press, its release and the timeouts cannot interleave.
 */
class DegasUdfpsHandler : public UdfpsHandler {
  public:
    void init(fingerprint_device_t* device) override {
        mDevice = device;
        mTouch.reset(open(kTouchDev, O_RDWR | O_CLOEXEC));
        mDisp.reset(open(kDispFeatureDev, O_RDWR | O_CLOEXEC));
        if (mTouch < 0) PLOG(ERROR) << "open " << kTouchDev;
        if (mDisp < 0) PLOG(ERROR) << "open " << kDispFeatureDev;
        std::thread(&DegasUdfpsHandler::run, this).detach();
    }

    void onFingerDown(uint32_t /*x*/, uint32_t /*y*/, float /*minor*/, float /*major*/) override {
        post(Request::kDown);
    }

    void onFingerUp() override { post(Request::kUp); }

    void cancel() override { post(Request::kUp); }

    void onAcquired(int32_t result, int32_t vendorCode) override {
        switch (static_cast<AcquiredInfo>(result)) {
            case AcquiredInfo::GOOD:
            case AcquiredInfo::PARTIAL:
            case AcquiredInfo::INSUFFICIENT:
            case AcquiredInfo::SENSOR_DIRTY:
            case AcquiredInfo::TOO_SLOW:
            case AcquiredInfo::TOO_FAST:
            case AcquiredInfo::TOO_DARK:
            case AcquiredInfo::TOO_BRIGHT:
            case AcquiredInfo::IMMOBILE:
            case AcquiredInfo::LIFT_TOO_SOON:
                // The capture of this press is over.
                post(Request::kUp);
                break;
            default:
                break;
        }
        // Vendor codes 21 and 22: the sensor waits for a finger.
        if (vendorCode == 21 || vendorCode == 22) {
            post(Request::kArmTouch);
        }
    }

  private:
    enum class Request { kDown, kUp, kArmTouch };
    using TimePoint = steady_clock::time_point;

    void post(Request request) {
        {
            std::lock_guard lock(mLock);
            mQueue[mQueued++ % std::size(mQueue)] = request;
        }
        mWake.notify_one();
    }

    void run() {
        std::unique_lock lock(mLock);
        size_t next = 0;
        while (true) {
            auto deadline = earliestDeadline();
            if (next == mQueued) {
                if (deadline) {
                    mWake.wait_until(lock, *deadline);
                } else {
                    mWake.wait(lock);
                }
            }
            while (next != mQueued) {
                Request request = mQueue[next++ % std::size(mQueue)];
                lock.unlock();
                handle(request);
                lock.lock();
            }
            lock.unlock();
            handleTimers();
            lock.lock();
        }
    }

    std::optional<TimePoint> earliestDeadline() const {
        std::optional<TimePoint> earliest;
        for (const auto& t : {mReadyAt, mTimeoutAt, mRepeatOffAt}) {
            if (t && (!earliest || *t < *earliest)) earliest = t;
        }
        return earliest;
    }

    void handle(Request request) {
        switch (request) {
            case Request::kDown:
                LOG(INFO) << "finger down";
                mPressed = true;
                extCmd(kCmdFodPressStatus, 1);
                setLocalHbm(MI_DISP_LHBM_WHITE_1000NIT);
                setTouchFod(true);
                mReadyAt = steady_clock::now() + kLhbmSettle;
                mTimeoutAt = steady_clock::now() + kPressTimeout;
                mRepeatOffAt.reset();
                break;
            case Request::kUp:
                if (mPressed) LOG(INFO) << "finger up";
                release();
                mRepeatOffAt = steady_clock::now() + kOffRepeat;
                break;
            case Request::kArmTouch:
                setTouchFod(true);
                break;
        }
    }

    void handleTimers() {
        auto now = steady_clock::now();
        if (mReadyAt && now >= *mReadyAt) {
            mReadyAt.reset();
            extCmd(kCmdNit, kNit1000);
        }
        if (mTimeoutAt && now >= *mTimeoutAt) {
            LOG(INFO) << "no finger up, turning the light off";
            release();
        }
        if (mRepeatOffAt && now >= *mRepeatOffAt) {
            mRepeatOffAt.reset();
            setLocalHbm(MI_DISP_LHBM_OFF_FINGER_UP);
            extCmd(kCmdNit, kNitOff);
        }
    }

    void release() {
        mPressed = false;
        mReadyAt.reset();
        mTimeoutAt.reset();
        extCmd(kCmdFodPressStatus, 0);
        setLocalHbm(MI_DISP_LHBM_OFF_FINGER_UP);
        extCmd(kCmdNit, kNitOff);
        setTouchFod(false);
    }

    void extCmd(int32_t cmd, int32_t param) {
        if (mDevice && mDevice->extCmd) mDevice->extCmd(mDevice, cmd, param);
    }

    void setLocalHbm(uint32_t value) {
        struct mi_disp_local_hbm_req req = {
                .base = {.flag = 0, .disp_id = 0},
                .local_hbm_value = value,
        };
        if (ioctl(mDisp.get(), MI_DISP_IOCTL_SET_LOCAL_HBM, &req) < 0) {
            PLOG(ERROR) << "local HBM " << value;
        }
    }

    void setTouchFod(bool pressed) {
        int buf[XIAOMI_TOUCH_BUF_SIZE] = {0, XIAOMI_TOUCH_MODE_FOD_ENABLE, pressed ? 1 : 0};
        if (ioctl(mTouch.get(), XIAOMI_TOUCH_IOC_SET_CUR_VALUE, &buf) < 0) {
            PLOG(ERROR) << "touch FOD mode " << pressed;
        }
    }

    fingerprint_device_t* mDevice = nullptr;
    android::base::unique_fd mTouch;
    android::base::unique_fd mDisp;

    std::mutex mLock;
    std::condition_variable mWake;
    Request mQueue[16];
    size_t mQueued = 0;

    // Only touched by the worker thread.
    bool mPressed = false;
    std::optional<TimePoint> mReadyAt;
    std::optional<TimePoint> mTimeoutAt;
    std::optional<TimePoint> mRepeatOffAt;
};

UdfpsHandler* create() {
    return new DegasUdfpsHandler();
}

void destroy(UdfpsHandler* handler) {
    delete handler;
}

}  // namespace

extern "C" UdfpsHandlerFactory UDFPS_HANDLER_FACTORY = {
        .create = create,
        .destroy = destroy,
};
