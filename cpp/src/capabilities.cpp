#include "expert_robot/capabilities.hpp"

#include <algorithm>
#include <regex>
#include <stdexcept>
#include <unordered_set>

namespace expert_robot {
namespace {

const std::regex kCapabilityId("^[a-z][a-z0-9_.-]*$");
const std::regex kVersion("^\\d+\\.\\d+\\.\\d+$");

void validate_ports(const std::vector<PortSpec>& ports, const char* kind) {
    std::unordered_set<std::string> names;
    for (const auto& port : ports) {
        if (port.name.empty()) {
            throw std::invalid_argument(std::string(kind) + " port name must be non-empty");
        }
        if (port.schema.empty()) {
            throw std::invalid_argument(
                std::string(kind) + " port '" + port.name + "' schema must be non-empty");
        }
        if (!names.insert(port.name).second) {
            throw std::invalid_argument(
                "duplicate " + std::string(kind) + " port name: " + port.name);
        }
    }
}

bool formally_verified(FormalStatus status) {
    return status == FormalStatus::KernelVerified || status == FormalStatus::Canonical;
}

} // namespace

bool CapabilityContract::exposed() const noexcept {
    return machine_callable && implemented && tests_passed;
}

std::vector<std::pair<std::string, std::string>>
CapabilityContract::compatible_outputs_for(const CapabilityContract& downstream) const {
    std::vector<std::pair<std::string, std::string>> matches;
    for (const auto& output : outputs) {
        for (const auto& input : downstream.inputs) {
            if (output.schema == input.schema) {
                matches.emplace_back(output.name, input.name);
            }
        }
    }
    return matches;
}

void validate_capability(const CapabilityContract& capability) {
    if (!std::regex_match(capability.capability_id, kCapabilityId)) {
        throw std::invalid_argument("invalid capability_id: " + capability.capability_id);
    }
    if (!std::regex_match(capability.version, kVersion)) {
        throw std::invalid_argument("invalid semantic version: " + capability.version);
    }

    validate_ports(capability.inputs, "input");
    validate_ports(capability.outputs, "output");

    if (capability.tests_passed && !capability.implemented) {
        throw std::invalid_argument(
            capability.capability_id + ": tests_passed cannot be true when implemented is false");
    }
    if (capability.implemented && capability.implementation.empty()) {
        throw std::invalid_argument(
            capability.capability_id + ": implemented capability must name an implementation");
    }
    if (formally_verified(capability.formal_status) && !capability.tests_passed) {
        throw std::invalid_argument(
            capability.capability_id + ": verified formal status requires passing tests");
    }
}

CapabilityRegistry::CapabilityRegistry(std::vector<CapabilityContract> capabilities)
    : capabilities_(std::move(capabilities)) {
    std::unordered_set<std::string> ids;
    for (const auto& capability : capabilities_) {
        validate_capability(capability);
        if (!ids.insert(capability.capability_id).second) {
            throw std::invalid_argument("duplicate capability_id entries are forbidden");
        }
    }
}

const CapabilityContract& CapabilityRegistry::get(std::string_view capability_id) const {
    const auto it = std::find_if(
        capabilities_.begin(),
        capabilities_.end(),
        [&](const CapabilityContract& item) {
            return item.capability_id == capability_id;
        });
    if (it == capabilities_.end()) {
        throw std::out_of_range("unknown capability_id");
    }
    return *it;
}

std::vector<CapabilityContract> CapabilityRegistry::exposed() const {
    std::vector<CapabilityContract> result;
    for (const auto& capability : capabilities_) {
        if (capability.exposed()) {
            result.push_back(capability);
        }
    }
    return result;
}

const std::vector<CapabilityContract>& CapabilityRegistry::all() const noexcept {
    return capabilities_;
}

} // namespace expert_robot
