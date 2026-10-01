#pragma once

#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace expert_robot {

enum class FormalStatus {
    Experimental,
    Engineering,
    KernelVerified,
    Canonical,
};

struct PortSpec {
    std::string name;
    std::string schema;
    bool required{true};
};

struct CapabilityContract {
    std::string capability_id;
    std::string version;
    std::vector<PortSpec> inputs;
    std::vector<PortSpec> outputs;
    bool machine_callable{false};
    bool implemented{false};
    bool tests_passed{false};
    FormalStatus formal_status{FormalStatus::Experimental};
    std::string implementation;

    [[nodiscard]] bool exposed() const noexcept;
    [[nodiscard]] std::vector<std::pair<std::string, std::string>>
    compatible_outputs_for(const CapabilityContract& downstream) const;
};

void validate_capability(const CapabilityContract& capability);

class CapabilityRegistry {
public:
    explicit CapabilityRegistry(std::vector<CapabilityContract> capabilities);

    [[nodiscard]] const CapabilityContract& get(std::string_view capability_id) const;
    [[nodiscard]] std::vector<CapabilityContract> exposed() const;
    [[nodiscard]] const std::vector<CapabilityContract>& all() const noexcept;

private:
    std::vector<CapabilityContract> capabilities_;
};

} // namespace expert_robot
