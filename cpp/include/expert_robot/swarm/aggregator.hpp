#pragma once

#include "expert_robot/swarm/task.hpp"

#include <cstddef>
#include <string>
#include <vector>

namespace expert_robot::swarm {

struct AggregatedCandidate {
    std::string fingerprint;
    std::string output;
    std::vector<AgentRole> supporting_roles;
    std::size_t support_count{0};
};

[[nodiscard]] std::vector<AggregatedCandidate> aggregate_results(
    const std::vector<AgentResult>& results);

} // namespace expert_robot::swarm
