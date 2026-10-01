#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot {

struct SearchProblem {
    std::string statement;
    std::string candidate_name{"MathAI_Search_Candidate"};
    std::vector<std::string> imports{"MathAI"};
    std::vector<std::string> context_declarations;

    // Trusted controller-supplied tactics tried before the configured base
    // strategy list. They are still compiled by Lean and cannot establish
    // proof truth on their own.
    std::vector<std::string> preferred_strategies;
};

struct SearchAttempt {
    std::string tactic;
    bool success{false};
    int exit_code{1};
    std::string output;
};

struct SearchResult {
    SearchProblem problem;
    bool success{false};
    std::optional<std::string> tactic;
    std::optional<std::string> proof;
    std::vector<SearchAttempt> attempts;
};

struct LeanRunResult {
    int exit_code{1};
    std::string output;
};

class ILeanRunner {
public:
    virtual ~ILeanRunner() = default;
    virtual LeanRunResult run(std::string_view source) = 0;
};

class LeanSubprocessRunner final : public ILeanRunner {
public:
    explicit LeanSubprocessRunner(std::filesystem::path root, int timeout_seconds = 20);

    LeanRunResult run(std::string_view source) override;

private:
    std::filesystem::path root_;
    int timeout_seconds_{20};
};

struct ProofSearchConfig {
    std::vector<std::string> strategies;
    int timeout_seconds{20};
};

[[nodiscard]] ProofSearchConfig load_proof_search_config(const std::filesystem::path& path);

class IProofSearcher {
public:
    virtual ~IProofSearcher() = default;
    [[nodiscard]] virtual SearchResult search(const SearchProblem& problem) = 0;
};

class DeterministicProofSearch final : public IProofSearcher {
public:
    DeterministicProofSearch(std::vector<std::string> strategies, ILeanRunner& runner);

    [[nodiscard]] static std::string render(const SearchProblem& problem, std::string_view tactic);
    [[nodiscard]] SearchResult search(const SearchProblem& problem) override;

private:
    std::vector<std::string> strategies_;
    ILeanRunner& runner_;
};

} // namespace expert_robot
