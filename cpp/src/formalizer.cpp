#include "expert_robot/formalizer.hpp"

#include <algorithm>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace expert_robot {
namespace {

const std::regex kQualifiedName(
    "^[A-Za-z_][A-Za-z0-9_]*(\\.[A-Za-z_][A-Za-z0-9_]*)*$");
const std::regex kSimpleName("^[A-Za-z_][A-Za-z0-9_']*$");
const std::regex kForbidden(
    "(^|[^A-Za-z0-9_])(sorry|admit|axiom|unsafe|set_option)([^A-Za-z0-9_]|$)|#",
    std::regex_constants::icase);

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1U);
}

void validate_lean_expression(const std::string& fragment, const char* label) {
    if (fragment.empty()) {
        throw std::invalid_argument(std::string(label) + " must be non-empty");
    }
    if (fragment.find('\0') != std::string::npos) {
        throw std::invalid_argument(std::string(label) + " contains a null byte");
    }
    if (fragment.find('\n') != std::string::npos ||
        fragment.find('\r') != std::string::npos) {
        throw std::invalid_argument(
            std::string(label) + " must be a single Lean expression");
    }
    if (contains_forbidden_lean_fragment(fragment)) {
        throw std::invalid_argument(
            std::string(label) + " contains a forbidden Lean token");
    }
}

} // namespace

bool contains_forbidden_lean_fragment(std::string_view fragment) {
    return std::regex_search(
        std::string(fragment),
        kForbidden);
}

void validate_binder(Binder& binder) {
    binder.name = trim(std::move(binder.name));
    binder.type = trim(std::move(binder.type));

    if (!std::regex_match(binder.name, kSimpleName)) {
        throw std::invalid_argument("invalid Lean binder name: " + binder.name);
    }
    validate_lean_expression(binder.type, "binder type");
}

void validate_formalization_proposal(FormalizationProposal& proposal) {
    proposal.name = trim(std::move(proposal.name));
    proposal.name_space = trim(std::move(proposal.name_space));
    proposal.proposition = trim(std::move(proposal.proposition));
    proposal.domain = trim(std::move(proposal.domain));
    proposal.rationale = trim(std::move(proposal.rationale));

    if (proposal.domain.empty()) proposal.domain = "unknown";

    if (!std::regex_match(proposal.name, kSimpleName)) {
        throw std::invalid_argument("invalid theorem name: " + proposal.name);
    }
    if (!std::regex_match(proposal.name_space, kQualifiedName)) {
        throw std::invalid_argument("invalid theorem namespace: " + proposal.name_space);
    }
    validate_lean_expression(proposal.proposition, "proposition");

    if (proposal.binders.size() > 64U) {
        throw std::invalid_argument("proposal has too many binders");
    }

    std::unordered_set<std::string> binder_names;
    for (auto& binder : proposal.binders) {
        validate_binder(binder);
        if (!binder_names.insert(binder.name).second) {
            throw std::invalid_argument("duplicate binder names are forbidden");
        }
    }

    if (proposal.imports.empty()) {
        throw std::invalid_argument("imports must be non-empty");
    }

    std::vector<std::string> imports;
    for (auto module : proposal.imports) {
        module = trim(std::move(module));
        if (!std::regex_match(module, kQualifiedName)) {
            throw std::invalid_argument("invalid Lean import: " + module);
        }
        if (std::find(imports.begin(), imports.end(), module) == imports.end()) {
            imports.push_back(std::move(module));
        }
    }
    proposal.imports = std::move(imports);
}

std::string FormalizationProposal::statement() const {
    std::ostringstream out;
    for (const auto& binder : binders) {
        out << "(" << binder.name << " : " << binder.type << ") ";
    }
    out << ": " << proposition;
    return out.str();
}

std::string FormalizationProposal::qualified_name() const {
    return name_space + "." + name;
}

std::string render_declaration(
    const FormalizationProposal& proposal,
    std::string_view proof) {
    const std::string declaration =
        "theorem " + proposal.qualified_name() + " " +
        proposal.statement() + " := " + std::string(proof);
    if (contains_forbidden_lean_fragment(declaration)) {
        throw std::invalid_argument(
            "generated declaration contains forbidden Lean tokens");
    }
    return declaration;
}

FormalizationResult formalize(
    FormalizationProposal proposal,
    IProofSearcher& searcher,
    const std::vector<std::string>& context_declarations) {
    validate_formalization_proposal(proposal);

    SearchProblem problem;
    problem.statement = proposal.statement();
    problem.candidate_name = "MathAI_Formalization_Candidate";
    problem.imports = proposal.imports;
    problem.context_declarations = context_declarations;

    auto search = searcher.search(problem);
    if (!search.success || !search.proof.has_value()) {
        return FormalizationResult{
            .proposal = std::move(proposal),
            .search = std::move(search),
            .lean_source = std::nullopt,
            .lean_declaration = std::nullopt,
            .trusted = false,
        };
    }

    const std::string declaration =
        render_declaration(proposal, *search.proof);

    std::ostringstream source;
    for (const auto& module : proposal.imports) {
        source << "import " << module << "\n";
    }
    source
        << "\nnamespace " << proposal.name_space << "\n\n"
        << "theorem " << proposal.name << " " << proposal.statement()
        << " := " << *search.proof << "\n\n"
        << "end " << proposal.name_space << "\n";

    return FormalizationResult{
        .proposal = std::move(proposal),
        .search = std::move(search),
        .lean_source = source.str(),
        .lean_declaration = declaration,
        .trusted = false,
    };
}

} // namespace expert_robot
