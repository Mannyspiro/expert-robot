#pragma once

#include "expert_robot/proof_search.hpp"

#include <filesystem>
#include <string>
#include <vector>

struct sqlite3;

namespace expert_robot {

struct StrategyStats {
    std::string tactic;
    int successes{0};
    int failures{0};

    [[nodiscard]] int attempts() const noexcept { return successes + failures; }
};

struct ProofMemorySummary {
    int schema_version{1};
    long long attempts{0};
    long long goals{0};
    long long successful_attempts{0};
};

[[nodiscard]] std::string goal_fingerprint(const SearchProblem& problem);

class ProofMemory {
public:
    explicit ProofMemory(std::filesystem::path path);
    ~ProofMemory();

    ProofMemory(const ProofMemory&) = delete;
    ProofMemory& operator=(const ProofMemory&) = delete;

    void record_result(const SearchResult& result);
    [[nodiscard]] std::vector<StrategyStats> stats_for(const SearchProblem& problem) const;
    [[nodiscard]] std::vector<std::string> order_strategies(
        const SearchProblem& problem,
        const std::vector<std::string>& base_strategies) const;
    [[nodiscard]] ProofMemorySummary summary() const;

private:
    std::filesystem::path path_;
    sqlite3* db_{nullptr};

    void initialize();
};

class MemoryGuidedProofSearch {
public:
    MemoryGuidedProofSearch(
        std::vector<std::string> base_strategies,
        ILeanRunner& runner,
        ProofMemory& memory);

    [[nodiscard]] SearchResult search(const SearchProblem& problem);

private:
    std::vector<std::string> base_strategies_;
    ILeanRunner& runner_;
    ProofMemory& memory_;
};

} // namespace expert_robot
