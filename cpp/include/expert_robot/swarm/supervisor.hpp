#pragma once

#include "expert_robot/swarm/agent.hpp"

#include <cstddef>
#include <unordered_map>
#include <vector>

namespace expert_robot::swarm {

struct AgentRoleHash {
    std::size_t operator()(AgentRole role) const noexcept {
        return static_cast<std::size_t>(role);
    }
};

struct SwarmLimits {
    std::size_t max_parallel_agents{4};
    std::size_t max_total_tasks{16};
    std::size_t max_depth{3};
    std::size_t max_children_per_parent{6};
    bool serialize_shared_backend{true};
};

void validate_swarm_limits(const SwarmLimits& limits);

class SwarmSupervisor {
public:
    using BackendMap = std::unordered_map<
        AgentRole,
        ITextGenerationBackend*,
        AgentRoleHash>;

    SwarmSupervisor(
        BackendMap backends,
        SwarmLimits limits = {});

    [[nodiscard]] std::vector<AgentResult> run_batch(
        const std::vector<AgentTask>& tasks) const;

    [[nodiscard]] const SwarmLimits& limits() const noexcept;

private:
    [[nodiscard]] ITextGenerationBackend& backend_for(
        AgentRole role) const;

    BackendMap backends_;
    SwarmLimits limits_;
};

} // namespace expert_robot::swarm
