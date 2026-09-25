#pragma once

#include "expert_robot/skills/math_skill.hpp"
#include "expert_robot/text_generation.hpp"

#include <optional>
#include <string>
#include <vector>

namespace expert_robot::skills {

struct SkillProposalContext {
    std::string recurring_pattern;
    std::string useful_method;
    std::vector<std::string> existing_skill_ids;
};

struct SkillProposalResult {
    bool proposed{false};
    std::optional<MathSkill> skill;
    std::string raw_output;
};

class ModelSkillProposer {
public:
    explicit ModelSkillProposer(
        ITextGenerationBackend& backend);

    [[nodiscard]] SkillProposalResult propose(
        const SkillProposalContext& context);

private:
    ITextGenerationBackend& backend_;
};

[[nodiscard]] SkillProposalResult
parse_skill_proposal_json(
    std::string_view json);

} // namespace expert_robot::skills
