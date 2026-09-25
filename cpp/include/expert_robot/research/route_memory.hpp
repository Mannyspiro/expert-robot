#pragma once

#include "expert_robot/research/route_planner.hpp"

#include <filesystem>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace expert_robot::research {

struct RouteOutcome {
    std::string route_id;
    ProofRouteKind kind{ProofRouteKind::ReuseVerifiedTheorem};
    std::string domain;

    bool verified_progress{false};
    bool target_verified{false};
    bool dead_end_escaped{false};

    double resource_cost{0.0};
};

struct RouteExperience {
    ProofRouteKind kind{ProofRouteKind::ReuseVerifiedTheorem};
    std::string domain;

    long long attempts{0};
    long long verified_progresses{0};
    long long target_verifications{0};
    long long dead_end_escapes{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double smoothed_verified_rate() const noexcept;
    [[nodiscard]] double smoothed_target_rate() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
};

struct RouteSequenceOutcome {
    std::string sequence_id;
    std::string domain;

    bool verified_progress{false};
    bool target_verified{false};
    bool dead_end_escaped{false};

    double resource_cost{0.0};
};

struct RouteSequenceExperience {
    std::string sequence_id;
    std::string domain;

    long long attempts{0};
    long long verified_progresses{0};
    long long target_verifications{0};
    long long dead_end_escapes{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double smoothed_verified_rate() const noexcept;
    [[nodiscard]] double smoothed_target_rate() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
};

struct ResearchStrategyOutcome {
    std::string strategy_id;
    std::string signature;
    std::string domain;

    bool verified_progress{false};
    bool target_verified{false};
    bool dead_end_escaped{false};

    double resource_cost{0.0};
};

struct ResearchStrategyExperience {
    std::string strategy_id;
    std::string signature;
    std::string domain;

    long long attempts{0};
    long long verified_progresses{0};
    long long target_verifications{0};
    long long dead_end_escapes{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double smoothed_verified_rate() const noexcept;
    [[nodiscard]] double smoothed_target_rate() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
};

struct ResearchStrategyContextOutcome {
    std::string strategy_id;
    std::string signature;
    std::string context_key;

    bool verified_progress{false};
    bool target_verified{false};
    bool dead_end_escaped{false};

    double resource_cost{0.0};
};

struct ResearchStrategyContextExperience {
    std::string strategy_id;
    std::string signature;
    std::string context_key;

    long long attempts{0};
    long long verified_progresses{0};
    long long target_verifications{0};
    long long dead_end_escapes{0};

    double total_resource_cost{0.0};

    [[nodiscard]] double smoothed_verified_rate() const noexcept;
    [[nodiscard]] double smoothed_target_rate() const noexcept;
    [[nodiscard]] double average_resource_cost() const noexcept;
};

class RouteOutcomeLedger {
public:
    explicit RouteOutcomeLedger(
        std::filesystem::path path);
    ~RouteOutcomeLedger();

    RouteOutcomeLedger(
        const RouteOutcomeLedger&) = delete;
    RouteOutcomeLedger& operator=(
        const RouteOutcomeLedger&) = delete;

    void record(const RouteOutcome& outcome);
    void record_sequence(const RouteSequenceOutcome& outcome);
    void record_strategy(const ResearchStrategyOutcome& outcome);
    void record_strategy_context(
        const ResearchStrategyContextOutcome& outcome);

    [[nodiscard]] RouteExperience experience(
        ProofRouteKind kind,
        std::string_view domain) const;

    [[nodiscard]] std::vector<RouteExperience> all_experience() const;

    [[nodiscard]] RouteSequenceExperience sequence_experience(
        std::string_view sequence_id,
        std::string_view domain) const;

    [[nodiscard]] std::vector<RouteSequenceExperience>
    all_sequence_experience() const;

    [[nodiscard]] ResearchStrategyExperience strategy_experience(
        std::string_view strategy_id,
        std::string_view domain) const;

    [[nodiscard]] std::vector<ResearchStrategyExperience>
    all_strategy_experience() const;

    [[nodiscard]] ResearchStrategyContextExperience
    strategy_context_experience(
        std::string_view strategy_id,
        std::string_view context_key) const;

    [[nodiscard]] std::vector<ResearchStrategyContextExperience>
    all_strategy_context_experience() const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::research
