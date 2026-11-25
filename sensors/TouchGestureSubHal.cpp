/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#define LOG_TAG "sensors.degas"

#include <V2_1/SubHal.h>
#include <android-base/unique_fd.h>
#include <log/log.h>
#include <utils/SystemClock.h>

#include <dirent.h>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/epoll.h>
#include <sys/eventfd.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include <cerrno>
#include <cstdio>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

using ::android::sp;
using ::android::base::unique_fd;
using ::android::hardware::hidl_handle;
using ::android::hardware::hidl_string;
using ::android::hardware::hidl_vec;
using ::android::hardware::Return;
using ::android::hardware::Void;
using ::android::hardware::sensors::V1_0::OperationMode;
using ::android::hardware::sensors::V1_0::RateLevel;
using ::android::hardware::sensors::V1_0::Result;
using ::android::hardware::sensors::V1_0::SensorFlagBits;
using ::android::hardware::sensors::V1_0::SharedMemInfo;
using ::android::hardware::sensors::V2_1::Event;
using ::android::hardware::sensors::V2_1::SensorInfo;
using ::android::hardware::sensors::V2_1::SensorType;
using ::android::hardware::sensors::V2_1::implementation::IHalProxyCallback;
using ::android::hardware::sensors::V2_1::implementation::ISensorsSubHal;

namespace {

/*
 * While the panel is dozing or off, the touch controller of the Xiaomi 14T
 * only looks for a few gestures and its driver reports them as keys of the
 * touch input device. A dozing system does not act on those keys. This
 * sub-HAL turns two of them into one-shot wake-up sensors, which is the form
 * SystemUI's doze code expects:
 *
 *  - a finger on the fingerprint sensor (config_dozeUdfpsLongPressSensorType),
 *    so that the fingerprint can be read from the always-on display;
 *  - a tap anywhere on the panel (config_dozeTapSensorType).
 */

// The driver's key for "finger on the fingerprint sensor".
constexpr uint16_t kKeyFingerOnSensor = 0x152;
// The driver's key for a single tap.
constexpr uint16_t kKeyTap = KEY_GOTO;

// The touch device reports positions finer than a pixel; they are scaled to
// the panel, which is what SystemUI wants.
constexpr float kPanelWidth = 1220.0f;
constexpr float kPanelHeight = 2712.0f;

// How often to look for the touch device again if it could not be opened.
constexpr int kRetryMs = 1000;

enum SensorIndex : size_t {
    kFingerOnSensor = 0,
    kTap = 1,
    kSensorCount = 2,
};

constexpr int32_t kTypeBase = static_cast<int32_t>(SensorType::DEVICE_PRIVATE_BASE) + 0x6467;

struct SensorDescription {
    const char* name;
    const char* type;
};

constexpr SensorDescription kSensors[kSensorCount] = {
        {"Fingerprint Sensor Touch", "com.nyxianglyph.sensor.udfps"},
        {"Screen Tap", "com.nyxianglyph.sensor.tap"},
};

int32_t handleOf(size_t index) {
    return static_cast<int32_t>(index) + 1;
}

SensorType typeOf(size_t index) {
    return static_cast<SensorType>(kTypeBase + static_cast<int32_t>(index));
}

bool hasKey(int fd, uint16_t key) {
    unsigned long bits[KEY_MAX / (8 * sizeof(unsigned long)) + 1] = {};
    if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(bits)), bits) < 0) return false;
    return bits[key / (8 * sizeof(unsigned long))] & (1UL << (key % (8 * sizeof(unsigned long))));
}

int32_t axisMaximum(int fd, unsigned int axis) {
    struct input_absinfo info = {};
    if (ioctl(fd, EVIOCGABS(axis), &info) < 0) return 0;
    return info.maximum;
}

// One report of the touch device, from the first event to SYN_REPORT.
struct Report {
    bool fingerOnSensor = false;
    bool tap = false;
    bool hasX = false;
    bool hasY = false;
    int32_t x = 0;
    int32_t y = 0;
    int32_t major = 0;
    int32_t minor = 0;
};

class TouchGestureSubHal : public ISensorsSubHal {
  public:
    TouchGestureSubHal() {
        mWake.reset(eventfd(0, EFD_CLOEXEC | EFD_NONBLOCK));
        if (mWake < 0) ALOGE("eventfd: %s", strerror(errno));
    }

    Return<void> getSensorsList_2_1(getSensorsList_2_1_cb _hidl_cb) override {
        std::vector<SensorInfo> sensors;
        for (size_t i = 0; i < kSensorCount; i++) {
            SensorInfo info = {};
            info.sensorHandle = handleOf(i);
            info.name = kSensors[i].name;
            info.vendor = "nyxianglyph";
            info.version = 1;
            info.type = typeOf(i);
            info.typeAsString = kSensors[i].type;
            info.maxRange = 4096.0f;
            info.resolution = 1.0f;
            info.power = 0.0f;
            // One-shot sensors have no sampling rate.
            info.minDelay = -1;
            info.maxDelay = 0;
            info.fifoReservedEventCount = 0;
            info.fifoMaxEventCount = 0;
            info.requiredPermission = "";
            info.flags = static_cast<uint32_t>(SensorFlagBits::ONE_SHOT_MODE) |
                         static_cast<uint32_t>(SensorFlagBits::WAKE_UP);
            sensors.push_back(info);
        }
        _hidl_cb(sensors);
        return Void();
    }

    Return<Result> setOperationMode(OperationMode mode) override {
        return mode == OperationMode::NORMAL ? Result::OK : Result::BAD_VALUE;
    }

    Return<Result> activate(int32_t sensorHandle, bool enabled) override {
        const size_t index = static_cast<size_t>(sensorHandle - 1);
        if (sensorHandle < 1 || index >= kSensorCount) return Result::BAD_VALUE;
        {
            std::lock_guard lock(mLock);
            mArmed[index] = enabled;
        }
        wakeReader();
        return Result::OK;
    }

    Return<Result> batch(int32_t sensorHandle, int64_t /*samplingPeriodNs*/,
                         int64_t /*maxReportLatencyNs*/) override {
        return sensorHandle >= 1 && static_cast<size_t>(sensorHandle - 1) < kSensorCount
                       ? Result::OK
                       : Result::BAD_VALUE;
    }

    // One-shot sensors cannot be flushed.
    Return<Result> flush(int32_t /*sensorHandle*/) override { return Result::BAD_VALUE; }

    Return<Result> injectSensorData_2_1(const Event& /*event*/) override {
        return Result::INVALID_OPERATION;
    }

    Return<void> registerDirectChannel(const SharedMemInfo& /*mem*/,
                                       registerDirectChannel_cb _hidl_cb) override {
        _hidl_cb(Result::INVALID_OPERATION, -1);
        return Void();
    }

    Return<Result> unregisterDirectChannel(int32_t /*channelHandle*/) override {
        return Result::INVALID_OPERATION;
    }

    Return<void> configDirectReport(int32_t /*sensorHandle*/, int32_t /*channelHandle*/,
                                    RateLevel /*rate*/, configDirectReport_cb _hidl_cb) override {
        _hidl_cb(Result::INVALID_OPERATION, 0);
        return Void();
    }

    Return<void> debug(const hidl_handle& fd, const hidl_vec<hidl_string>& /*args*/) override {
        if (fd.getNativeHandle() == nullptr || fd->numFds < 1) return Void();
        std::lock_guard lock(mLock);
        dprintf(fd->data[0], "degas touch gestures: finger on sensor armed=%d, tap armed=%d, "
                             "touch device open=%d\n",
                mArmed[kFingerOnSensor], mArmed[kTap], mDeviceOpen);
        return Void();
    }

    const std::string getName() override { return "degas"; }

    // Called again whenever the sensor service restarts.
    Return<Result> initialize(const sp<IHalProxyCallback>& halProxyCallback) override {
        {
            std::lock_guard lock(mLock);
            mCallback = halProxyCallback;
            for (bool& armed : mArmed) armed = false;
            if (!mStarted) {
                mStarted = true;
                std::thread(&TouchGestureSubHal::run, this).detach();
            }
        }
        wakeReader();
        return Result::OK;
    }

  private:
    void wakeReader() {
        uint64_t one = 1;
        if (write(mWake.get(), &one, sizeof(one)) < 0 && errno != EAGAIN) {
            ALOGE("wake the reader: %s", strerror(errno));
        }
    }

    bool anyArmed() {
        std::lock_guard lock(mLock);
        for (bool armed : mArmed) {
            if (armed) return true;
        }
        return false;
    }

    // The touch device is the one that has the fingerprint key; its name
    // depends on which controller the unit was built with.
    unique_fd openTouchDevice() {
        std::unique_ptr<DIR, int (*)(DIR*)> dir(opendir("/dev/input"), closedir);
        if (!dir) {
            ALOGE("/dev/input: %s", strerror(errno));
            return unique_fd();
        }
        while (dirent* entry = readdir(dir.get())) {
            if (strncmp(entry->d_name, "event", 5) != 0) continue;
            const std::string path = std::string("/dev/input/") + entry->d_name;
            unique_fd fd(open(path.c_str(), O_RDONLY | O_CLOEXEC | O_NONBLOCK));
            if (fd < 0 || !hasKey(fd.get(), kKeyFingerOnSensor)) continue;
            mMaxX = axisMaximum(fd.get(), ABS_MT_POSITION_X);
            mMaxY = axisMaximum(fd.get(), ABS_MT_POSITION_Y);
            ALOGI("touch device %s", path.c_str());
            return fd;
        }
        return unique_fd();
    }

    // The device is only kept open while a sensor is armed, which is while
    // the system dozes; in normal use no touch event wakes this thread.
    void run() {
        unique_fd epoll(epoll_create1(EPOLL_CLOEXEC));
        struct epoll_event wakeEvent = {.events = EPOLLIN, .data = {.u32 = 0}};
        if (epoll < 0 || epoll_ctl(epoll.get(), EPOLL_CTL_ADD, mWake.get(), &wakeEvent) < 0) {
            ALOGE("epoll: %s", strerror(errno));
            return;
        }

        unique_fd device;
        Report report;
        while (true) {
            const bool wanted = anyArmed();
            if (wanted && device < 0) {
                device = openTouchDevice();
                // The touch interrupt can be what woke the system; EPOLLWAKEUP
                // keeps it awake until the event has been handled.
                struct epoll_event deviceEvent = {.events = EPOLLIN | EPOLLWAKEUP,
                                                  .data = {.u32 = 1}};
                if (device >= 0 &&
                    epoll_ctl(epoll.get(), EPOLL_CTL_ADD, device.get(), &deviceEvent) < 0) {
                    ALOGE("watch the touch device: %s", strerror(errno));
                    device.reset();
                }
                report = Report();
            } else if (!wanted && device >= 0) {
                device.reset();  // closing it also removes it from the epoll set
            }
            setDeviceOpen(device >= 0);

            struct epoll_event events[2];
            const int timeout = (wanted && device < 0) ? kRetryMs : -1;
            const int count = epoll_wait(epoll.get(), events, 2, timeout);
            for (int i = 0; i < count; i++) {
                if (events[i].data.u32 == 0) {
                    uint64_t drained;
                    (void)read(mWake.get(), &drained, sizeof(drained));
                } else if (device >= 0 && !readReports(device.get(), &report)) {
                    device.reset();
                }
            }
        }
    }

    void setDeviceOpen(bool open) {
        std::lock_guard lock(mLock);
        mDeviceOpen = open;
    }

    // Returns false when the device is gone.
    bool readReports(int fd, Report* report) {
        struct input_event events[32];
        while (true) {
            const ssize_t size = read(fd, events, sizeof(events));
            if (size < 0) return errno == EAGAIN || errno == EINTR;
            if (size == 0) return true;
            const size_t count = static_cast<size_t>(size) / sizeof(events[0]);
            for (size_t i = 0; i < count; i++) handleEvent(events[i], report);
        }
    }

    void handleEvent(const struct input_event& event, Report* report) {
        switch (event.type) {
            case EV_KEY:
                if (event.value != 1) break;
                if (event.code == kKeyFingerOnSensor) report->fingerOnSensor = true;
                if (event.code == kKeyTap) report->tap = true;
                break;
            case EV_ABS:
                switch (event.code) {
                    case ABS_MT_POSITION_X:
                        report->x = event.value;
                        report->hasX = true;
                        break;
                    case ABS_MT_POSITION_Y:
                        report->y = event.value;
                        report->hasY = true;
                        break;
                    case ABS_MT_WIDTH_MAJOR:
                        report->major = event.value;
                        break;
                    case ABS_MT_WIDTH_MINOR:
                        report->minor = event.value;
                        break;
                }
                break;
            case EV_SYN:
                if (event.code != SYN_REPORT) break;
                if (report->fingerOnSensor) trigger(kFingerOnSensor, *report);
                if (report->tap) trigger(kTap, *report);
                *report = Report();
                break;
        }
    }

    void trigger(size_t index, const Report& report) {
        sp<IHalProxyCallback> callback;
        {
            std::lock_guard lock(mLock);
            if (!mArmed[index] || mCallback == nullptr) return;
            // A one-shot sensor disarms itself when it fires.
            mArmed[index] = false;
            callback = mCallback;
        }

        Event event = {};
        event.timestamp = ::android::elapsedRealtimeNano();
        event.sensorHandle = handleOf(index);
        event.sensorType = typeOf(index);
        // SystemUI reads the position from values 0 and 1 and the size of the
        // touch from values 3 and 4. A negative position means "unknown".
        const bool hasPosition = report.hasX && report.hasY && mMaxX > 0 && mMaxY > 0;
        event.u.data[0] = hasPosition ? report.x * kPanelWidth / (mMaxX + 1) : -1.0f;
        event.u.data[1] = hasPosition ? report.y * kPanelHeight / (mMaxY + 1) : -1.0f;
        event.u.data[3] = static_cast<float>(report.major);
        event.u.data[4] = static_cast<float>(report.minor);

        ALOGI("%s", kSensors[index].name);
        callback->postEvents({event}, callback->createScopedWakelock(true /* lock */));
    }

    std::mutex mLock;
    sp<IHalProxyCallback> mCallback;
    bool mArmed[kSensorCount] = {};
    bool mStarted = false;
    bool mDeviceOpen = false;
    unique_fd mWake;

    // Only touched by the reader thread.
    int32_t mMaxX = 0;
    int32_t mMaxY = 0;
};

}  // namespace

ISensorsSubHal* sensorsHalGetSubHal_2_1(uint32_t* version) {
    static TouchGestureSubHal subHal;
    *version = SUB_HAL_2_1_VERSION;
    return &subHal;
}
