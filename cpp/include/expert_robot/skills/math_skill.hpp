#pragma once

#include "expert_robot/imagination/idea.hpp"

#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::skills {

enum class SkillStage {
    Experimental,
    Qualified,
    Deprecated,
};

[[nodiscard]] std::string_view skill_stage_name(SkillStage stage);

struct MathSkill {
    std::string skill_id;
    std::string title;
    imagination::ImaginationLens lens{
        imagination::ImaginationLens::Analogy};
    swarm::AgentRole preferred_role{
        swarm::AgentRole::Mathematician};
    std::string procedure;
    bool requires_lean_verification{true};
    SkillStage stage{SkillStage::Experimental};
};

class MathSkillCatalog {
public:
    explicit MathSkillCatalog(
        std::vector<MathSkill> skills);

    [[nodiscard]] static MathSkillCatalog builtins();

    [[nodiscard]] const MathSkill& get(
        std::string_view skill_id) const;

    [[nodiscard]] std::vector<MathSkill> for_lens(
        imagination::ImaginationLens lens) const;

    [[nodiscard]] std::vector<MathSkill> qualified_for_lens(
        imagination::ImaginationLens lens) const;

    [[nodiscard]] const std::vector<MathSkill>& all() const noexcept;

private:
    std::vector<MathSkill> skills_;
};

} // namespace expert_robot::skills
