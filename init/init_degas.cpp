/*
 * Copyright (C) 2026 nyxianglyph
 *
 * SPDX-License-Identifier: Apache-2.0
 */

/*
 * HyperOS' init does two device-specific things while loading properties,
 * and the modem depends on both:
 *
 *  - it applies the whitelisted keys of the factory opcust partition's
 *    etc/carrier.prop (among them ro.product.vendor.name, which the modem
 *    uses to verify the IMEI signature: a wrong value leaves the SIMs
 *    without service, +ENVSIGERR);
 *  - it loads the MediaTek RSC properties of the region the bootloader
 *    passes in ro.boot.rsc (modem type, RATs).
 *
 * opcust is mounted read-only at /opcust in first stage (see fstab). No
 * value is hardcoded here: everything comes from the device itself.
 */

#include <fstream>
#include <set>
#include <string>

#include <android-base/file.h>
#include <android-base/logging.h>
#include <android-base/properties.h>
#include <android-base/strings.h>

#define _REALLY_INCLUDE_SYS__SYSTEM_PROPERTIES_H_
#include <sys/_system_properties.h>

#include "vendor_init.h"

using android::base::GetProperty;
using android::base::ReadFileToString;
using android::base::Split;
using android::base::StartsWith;
using android::base::Trim;

namespace {

constexpr const char* kCarrierProp = "/opcust/etc/carrier.prop";
constexpr const char* kCarrierWhitelist = "/opcust/etc/carrier_prop_white_keys_list";
constexpr const char* kRscDir = "/vendor/etc/rsc/";

void SetProperty(const std::string& key, const std::string& value) {
    prop_info* pi = const_cast<prop_info*>(__system_property_find(key.c_str()));
    int ret = pi ? __system_property_update(pi, value.c_str(), value.size())
                 : __system_property_add(key.c_str(), key.size(), value.c_str(), value.size());
    if (ret < 0) {
        LOG(ERROR) << "degas: failed to set " << key << "=" << value;
    }
}

// Calls fn(key, value) for every "key=value" line of a property file.
template <typename Fn>
bool ForEachProp(const std::string& path, Fn fn) {
    std::string content;
    if (!ReadFileToString(path, &content)) return false;
    for (const auto& raw : Split(content, "\n")) {
        std::string line = Trim(raw);
        if (line.empty() || line[0] == '#') continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        fn(Trim(line.substr(0, eq)), Trim(line.substr(eq + 1)));
    }
    return true;
}

void LoadCarrierProps() {
    std::string list;
    if (!ReadFileToString(kCarrierWhitelist, &list)) {
        LOG(WARNING) << "degas: " << kCarrierWhitelist << " not readable, opcust not mounted?";
        return;
    }
    std::set<std::string> allowed;
    for (const auto& key : Split(list, "\n")) {
        std::string k = Trim(key);
        // ro.boot.* comes from the bootloader and must stay as it is.
        if (!k.empty() && k[0] != '#' && !StartsWith(k, "ro.boot.")) allowed.insert(k);
    }
    ForEachProp(kCarrierProp, [&](const std::string& key, const std::string& value) {
        if (allowed.count(key)) {
            LOG(INFO) << "degas: carrier " << key << "=" << value;
            SetProperty(key, value);
        }
    });
}

void LoadRscProps() {
    std::string rsc = GetProperty("ro.boot.rsc", "");
    if (rsc.empty() || rsc.find('/') != std::string::npos || rsc.find("..") != std::string::npos) {
        rsc = "default";
    }
    std::string dir = std::string(kRscDir) + rsc + "/";
    // ro.prop overrides, rw.prop only provides defaults.
    if (!ForEachProp(dir + "ro.prop", SetProperty)) {
        LOG(WARNING) << "degas: no RSC props for " << rsc;
    }
    ForEachProp(dir + "rw.prop", [](const std::string& key, const std::string& value) {
        if (!__system_property_find(key.c_str())) SetProperty(key, value);
    });
}

}  // namespace

void vendor_load_properties() {
    LoadRscProps();
    LoadCarrierProps();
}
