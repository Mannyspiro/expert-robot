#pragma once

#include "expert_robot/proof_search.hpp"

#include <optional>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot {

struct Binder {
    std::string name;
    std::string type;

    bool operator==(const Binder&) const = default;
};

struct FormalizationProposal {
    std::string name;
    std::string name_space{"MathAI.Generated"};
    std::vector<Binder> binders;
    std::string proposition;
    std::vector<std::string> imports{"MathAI"};
    std::string domain{"unknown"};
    std::string rationale;

    [[nodiscard]] std::string statement() const;
    [[nodiscard]] std::string qualified_name() const;

    bool operator==(const FormalizationProposal&) const = default;
};

struct FormalizationResult {
    FormalizationProposal proposal;
    SearchResult search;
    std::optional<std::string> lean_source;
    std::optional<std::string> lean_declaration;
    bool trusted{false};

    [[nodiscard]] bool proven() const noexcept {
        return lean_declaration.has_value();
    }
};

void validate_binder(Binder& binder);
void validate_formalization_proposal(FormalizationProposal& proposal);

[[nodiscard]] bool contains_forbidden_lean_fragment(std::string_view fragment);
[[nodiscard]] std::string render_declaration(
    const FormalizationProposal& proposal,
    std::string_view proof);

[[nodiscard]] FormalizationResult formalize(
    FormalizationProposal proposal,
    IProofSearcher& searcher,
    const std::vector<std::string>& context_declarations = {},
    const std::vector<std::string>& preferred_strategies = {});

} // namespace expert_robot
