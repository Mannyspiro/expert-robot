#pragma once

#include "expert_robot/skills/math_skill.hpp"
#include "expert_robot/skills/skill_ledger.hpp"

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace expert_robot::skills {

struct SkillPromotionReport {
    MathSkill skill;
    SkillStats stats;
    SkillStage recommended{SkillStage::Experimental};
    bool requires_explicit_promotion{true};
    std::string rationale;
};

class ExperimentalSkillStore {
public:
    explicit ExperimentalSkillStore(std::filesystem::path path);
    ~ExperimentalSkillStore();

    ExperimentalSkillStore(const ExperimentalSkillStore&) = delete;
    ExperimentalSkillStore& operator=(const ExperimentalSkillStore&) = delete;

    void propose(
        MathSkill skill,
        std::string_view source);

    [[nodiscard]] std::vector<MathSkill> all() const;

    [[nodiscard]] MathSkill get(
        std::string_view skill_id) const;

    [[nodiscard]] SkillPromotionReport promotion_report(
        std::string_view skill_id,
        const SkillLedger& ledger,
        const SkillQualificationPolicy& policy = {}) const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::skills
