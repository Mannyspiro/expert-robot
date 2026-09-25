#pragma once

#include "expert_robot/cognition/controller.hpp"
#include "expert_robot/imagination/archive.hpp"
#include "expert_robot/imagination/memory.hpp"
#include "expert_robot/knowledge_graph.hpp"
#include "expert_robot/skills/math_skill.hpp"
#include "expert_robot/swarm/supervisor.hpp"

#include <cstddef>
#include <string>
#include <vector>

namespace expert_robot::imagination {

struct ImaginationConfig {
    std::size_t normal_lens_budget{4};
    std::size_t breakthrough_lens_budget{8};
    std::size_t skeptic_budget{6};
    std::size_t max_expensive_candidates{3};
    std::size_t archive_capacity_per_lens{2};

    double minimum_imagination_drive{0.18};
    int maximum_skeptic_risk{65};
};

struct ImaginationRequest {
    std::string request_id;
    std::string goal;
    std::vector<std::string> context;
    std::string focus_theorem;

    cognition::PersonalityProfile personality;
    cognition::CognitionCycle cognition;
    cognition::LogicalAssessment logic;
};

struct ImaginationRun {
    double imagination_drive{0.0};

    std::vector<ImaginationLens> selected_lenses;
    std::vector<IdeaCandidate> generated;
    std::vector<IdeaCandidate> archive_elites;
    std::vector<IdeaCandidate> shortlisted;

    bool skipped{false};
    std::string note;
};

void validate_imagination_config(const ImaginationConfig& config);

class ImaginationController {
public:
    ImaginationController(
        swarm::SwarmSupervisor& swarm,
        ImaginationConfig config = {},
        const KnowledgeGraph* theorem_graph = nullptr,
        skills::MathSkillCatalog skill_catalog =
            skills::MathSkillCatalog::builtins(),
        ImaginationMemory* memory = nullptr);

    [[nodiscard]] ImaginationRun run(
        const ImaginationRequest& request);

    [[nodiscard]] const QualityDiversityArchive& archive() const noexcept;

private:
    [[nodiscard]] double imagination_drive(
        const ImaginationRequest& request) const;

    [[nodiscard]] std::vector<ImaginationLens> choose_lenses(
        const ImaginationRequest& request,
        std::size_t budget) const;

    [[nodiscard]] std::vector<std::string> augmented_context(
        const ImaginationRequest& request) const;

    swarm::SwarmSupervisor& swarm_;
    ImaginationConfig config_;
    const KnowledgeGraph* theorem_graph_{nullptr};
    QualityDiversityArchive archive_;
    skills::MathSkillCatalog skills_;
    ImaginationMemory* memory_{nullptr};
};

} // namespace expert_robot::imagination
