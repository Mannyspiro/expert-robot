#pragma once

#include "expert_robot/research/state_machine.hpp"
#include "expert_robot/research/strategy_planner.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

namespace expert_robot::research {

struct DiscoveredResearchStrategy {
    std::string strategy_id;
    std::string signature;
    std::string title;
    std::vector<ProofRouteKind> steps;
};

[[nodiscard]] std::optional<DiscoveredResearchStrategy>
discover_research_strategy(
    const ResearchState& state,
    std::size_t max_steps = 3);

} // namespace expert_robot::research
