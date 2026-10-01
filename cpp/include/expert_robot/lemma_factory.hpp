#pragma once

#include "expert_robot/formalizer.hpp"

#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace expert_robot {

class ILemmaDecomposer {
public:
    virtual ~ILemmaDecomposer() = default;

    [[nodiscard]] virtual std::vector<FormalizationProposal> decompose(
        const FormalizationProposal& proposal,
        const FormalizationResult& failed_result) = 0;
};

[[nodiscard]] std::string proposal_fingerprint(
    const FormalizationProposal& proposal);

struct LemmaFactoryNode {
    FormalizationProposal proposal;
    std::size_t depth{0};
    std::string status;
    std::optional<FormalizationResult> initial_result;
    std::vector<LemmaFactoryNode> children;
    std::optional<FormalizationResult> retry_result;
    std::string note;

    [[nodiscard]] const FormalizationResult* proven_result() const noexcept;
    [[nodiscard]] bool proven() const noexcept;
    [[nodiscard]] std::vector<std::string> proof_declarations() const;
    [[nodiscard]] std::size_t node_count() const noexcept;
    [[nodiscard]] std::size_t proven_node_count() const noexcept;
};

class StaticLemmaDecomposer final : public ILemmaDecomposer {
public:
    using Plan = std::unordered_map<
        std::string,
        std::vector<FormalizationProposal>>;

    explicit StaticLemmaDecomposer(Plan mapping);

    [[nodiscard]] std::vector<FormalizationProposal> decompose(
        const FormalizationProposal& proposal,
        const FormalizationResult& failed_result) override;

private:
    Plan mapping_;
};

struct LemmaFactoryConfig {
    std::size_t max_depth{3};
    std::size_t max_children{6};
    std::size_t max_nodes{32};
};

void validate_lemma_factory_config(const LemmaFactoryConfig& config);

class RecursiveLemmaFactory {
public:
    RecursiveLemmaFactory(
        IProofSearcher& searcher,
        ILemmaDecomposer& decomposer,
        LemmaFactoryConfig config = {});

    [[nodiscard]] LemmaFactoryNode solve(FormalizationProposal proposal);

    [[nodiscard]] const LemmaFactoryConfig& config() const noexcept;

private:
    [[nodiscard]] LemmaFactoryNode solve_impl(
        FormalizationProposal proposal,
        std::size_t depth,
        const std::vector<std::string>& inherited_context,
        const std::unordered_set<std::string>& ancestors);

    IProofSearcher& searcher_;
    ILemmaDecomposer& decomposer_;
    LemmaFactoryConfig config_;
    std::size_t remaining_nodes_{0};
};

[[nodiscard]] std::string decomposition_prompt(
    const FormalizationProposal& proposal,
    const FormalizationResult& failed_result,
    std::size_t max_children = 6);

[[nodiscard]] std::vector<FormalizationProposal> parse_decomposition_json(
    std::string_view text,
    std::size_t max_children = 6);

} // namespace expert_robot
