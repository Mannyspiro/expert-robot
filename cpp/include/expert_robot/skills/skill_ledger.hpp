#pragma once

#include "expert_robot/skills/math_skill.hpp"

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace expert_robot::skills {

struct SkillOutcome {
    bool skeptic_passed{false};
    bool shortlisted{false};
    bool downstream_verified{false};
    bool downstream_failed{false};
};

struct SkillStats {
    std::string skill_id;
    long long attempts{0};
    long long skeptic_passes{0};
    long long shortlisted{0};
    long long downstream_verified{0};
    long long downstream_failed{0};

    [[nodiscard]] double verified_rate() const noexcept;
    [[nodiscard]] double shortlist_rate() const noexcept;
};

struct SkillQualificationPolicy {
    long long minimum_attempts{20};
    long long minimum_verified{3};
    double minimum_verified_rate{0.15};
    double minimum_shortlist_rate{0.20};
};

[[nodiscard]] SkillStage recommended_stage(
    const SkillStats& stats,
    const SkillQualificationPolicy& policy = {});

class SkillLedger {
public:
    explicit SkillLedger(std::filesystem::path path);
    ~SkillLedger();

    SkillLedger(const SkillLedger&) = delete;
    SkillLedger& operator=(const SkillLedger&) = delete;

    void record(
        std::string_view skill_id,
        const SkillOutcome& outcome);

    [[nodiscard]] SkillStats stats(
        std::string_view skill_id) const;

    [[nodiscard]] std::vector<SkillStats> all_stats() const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::skills
