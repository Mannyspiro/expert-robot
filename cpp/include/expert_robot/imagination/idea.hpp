#pragma once

#include "expert_robot/swarm/task.hpp"

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::imagination {

enum class ImaginationLens : std::size_t {
    Analogy = 0,
    Geometry,
    Algebra,
    Duality,
    Inversion,
    Generalization,
    Simplification,
    BoundaryCase,
    Spectral,
    Topological,
    Counterfactual,
    Construction,
    Lemma,
    Lacuna,
    Count
};

struct IdeaCandidate {
    std::string idea_id;
    ImaginationLens lens{ImaginationLens::Analogy};
    swarm::AgentRole source_role{swarm::AgentRole::Mathematician};
    std::string text;
    std::string skill_id;

    double novelty_score{0.0};
    double relevance_score{0.0};
    double quality_diversity_score{0.0};

    bool skeptic_valid{false};
    bool skeptic_keep{false};
    int skeptic_risk{100};
    std::string skeptic_critique;

    [[nodiscard]] double final_score() const noexcept;
};

[[nodiscard]] std::string_view lens_name(ImaginationLens lens);
[[nodiscard]] swarm::AgentRole role_for_lens(ImaginationLens lens);
[[nodiscard]] std::string lens_instruction(ImaginationLens lens);

} // namespace expert_robot::imagination
