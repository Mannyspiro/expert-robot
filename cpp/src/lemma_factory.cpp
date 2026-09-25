#include "expert_robot/lemma_factory.hpp"

#include "expert_robot/json_util.hpp"
#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <set>
#include <sstream>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace expert_robot {
namespace {

std::string canonical_string_array(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ",";
        out << "\"" << json_util::escape_ascii(values[i]) << "\"";
    }
    out << "]";
    return out.str();
}

std::string canonical_binders(const std::vector<Binder>& binders) {
    std::ostringstream out;
    out << "[";
    for (std::size_t i = 0; i < binders.size(); ++i) {
        if (i) out << ",";
        out << "{\"name\":\""
            << json_util::escape_ascii(binders[i].name)
            << "\",\"type\":\""
            << json_util::escape_ascii(binders[i].type)
            << "\"}";
    }
    out << "]";
    return out.str();
}


std::set<std::string> top_level_keys(const std::string& json) {
    std::set<std::string> keys;
    std::size_t i = 0;
    while (i < json.size() &&
           std::isspace(static_cast<unsigned char>(json[i]))) {
        ++i;
    }
    if (i >= json.size() || json[i] != '{') {
        throw std::invalid_argument("JSON value must be an object");
    }

    int depth = 0;
    bool in_string = false;
    bool escaped = false;

    for (; i < json.size(); ++i) {
        const char ch = json[i];

        if (in_string) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') in_string = false;
            continue;
        }

        if (ch == '{' || ch == '[') {
            ++depth;
            continue;
        }
        if (ch == '}' || ch == ']') {
            --depth;
            continue;
        }

        if (ch == '"' && depth == 1) {
            std::string key;
            bool key_escaped = false;
            std::size_t j = i + 1U;
            for (; j < json.size(); ++j) {
                const char kj = json[j];
                if (key_escaped) {
                    key.push_back(kj);
                    key_escaped = false;
                } else if (kj == '\\') {
                    key_escaped = true;
                } else if (kj == '"') {
                    break;
                } else {
                    key.push_back(kj);
                }
            }
            if (j >= json.size()) {
                throw std::invalid_argument("unterminated JSON object key");
            }
            std::size_t k = j + 1U;
            while (k < json.size() &&
                   std::isspace(static_cast<unsigned char>(json[k]))) {
                ++k;
            }
            if (k < json.size() && json[k] == ':') {
                keys.insert(std::move(key));
            }
            i = j;
        }
    }

    return keys;
}

FormalizationProposal proposal_from_json_object(const std::string& object) {
    static const std::set<std::string> allowed = {
        "name", "namespace", "binders", "proposition",
        "imports", "domain", "rationale"
    };
    const auto keys = top_level_keys(object);
    for (const auto& key : keys) {
        if (!allowed.contains(key)) {
            throw std::invalid_argument(
                "unknown proposal field in decomposition: " + key);
        }
    }

    FormalizationProposal proposal;
    proposal.name = json_util::string_field(object, "name");
    proposal.name_space =
        json_util::string_field(object, "namespace", "MathAI.Generated");
    proposal.proposition =
        json_util::string_field(object, "proposition");
    proposal.imports =
        json_util::string_array_field(object, "imports");
    proposal.domain =
        json_util::string_field(object, "domain", "unknown");
    proposal.rationale =
        json_util::string_field(object, "rationale");

    if (proposal.imports.empty()) {
        proposal.imports = {"MathAI"};
    }

    for (const auto& binder_object :
         json_util::object_array(object, "binders")) {
        proposal.binders.push_back(Binder{
            .name = json_util::string_field(binder_object, "name"),
            .type = json_util::string_field(binder_object, "type"),
        });
    }

    validate_formalization_proposal(proposal);
    return proposal;
}

void append_unique(
    std::vector<std::string>& destination,
    const std::vector<std::string>& source) {
    for (const auto& item : source) {
        if (std::find(destination.begin(), destination.end(), item) ==
            destination.end()) {
            destination.push_back(item);
        }
    }
}

} // namespace

std::string proposal_fingerprint(
    const FormalizationProposal& proposal_input) {
    auto proposal = proposal_input;
    validate_formalization_proposal(proposal);

    // Matches Python json.dumps(..., sort_keys=True, separators=(",", ":"))
    // with ensure_ascii=True. Top-level alphabetical key order is:
    // binders, imports, name, namespace, proposition.
    std::ostringstream canonical;
    canonical
        << "{\"binders\":" << canonical_binders(proposal.binders)
        << ",\"imports\":" << canonical_string_array(proposal.imports)
        << ",\"name\":\"" << json_util::escape_ascii(proposal.name) << "\""
        << ",\"namespace\":\"" << json_util::escape_ascii(proposal.name_space) << "\""
        << ",\"proposition\":\"" << json_util::escape_ascii(proposal.proposition) << "\"}";
    return sha256_hex(canonical.str());
}

const FormalizationResult* LemmaFactoryNode::proven_result() const noexcept {
    if (retry_result && retry_result->proven()) {
        return &*retry_result;
    }
    if (initial_result && initial_result->proven()) {
        return &*initial_result;
    }
    return nullptr;
}

bool LemmaFactoryNode::proven() const noexcept {
    return proven_result() != nullptr;
}

std::vector<std::string> LemmaFactoryNode::proof_declarations() const {
    std::vector<std::string> declarations;
    for (const auto& child : children) {
        append_unique(declarations, child.proof_declarations());
    }

    const auto* result = proven_result();
    if (result && result->lean_declaration) {
        if (std::find(
                declarations.begin(),
                declarations.end(),
                *result->lean_declaration) == declarations.end()) {
            declarations.push_back(*result->lean_declaration);
        }
    }
    return declarations;
}

std::size_t LemmaFactoryNode::node_count() const noexcept {
    std::size_t count = 1;
    for (const auto& child : children) {
        count += child.node_count();
    }
    return count;
}

std::size_t LemmaFactoryNode::proven_node_count() const noexcept {
    std::size_t count = proven() ? 1U : 0U;
    for (const auto& child : children) {
        count += child.proven_node_count();
    }
    return count;
}

StaticLemmaDecomposer::StaticLemmaDecomposer(Plan mapping)
    : mapping_(std::move(mapping)) {}

std::vector<FormalizationProposal> StaticLemmaDecomposer::decompose(
    const FormalizationProposal& proposal,
    const FormalizationResult&) {
    const auto it = mapping_.find(proposal.qualified_name());
    if (it == mapping_.end()) return {};
    return it->second;
}

void validate_lemma_factory_config(const LemmaFactoryConfig& config) {
    if (config.max_children == 0U) {
        throw std::invalid_argument("max_children must be positive");
    }
    if (config.max_nodes == 0U) {
        throw std::invalid_argument("max_nodes must be positive");
    }
}

RecursiveLemmaFactory::RecursiveLemmaFactory(
    IProofSearcher& searcher,
    ILemmaDecomposer& decomposer,
    LemmaFactoryConfig config)
    : searcher_(searcher),
      decomposer_(decomposer),
      config_(config),
      remaining_nodes_(config.max_nodes) {
    validate_lemma_factory_config(config_);
}

const LemmaFactoryConfig& RecursiveLemmaFactory::config() const noexcept {
    return config_;
}

LemmaFactoryNode RecursiveLemmaFactory::solve(
    FormalizationProposal proposal) {
    remaining_nodes_ = config_.max_nodes;
    return solve_impl(
        std::move(proposal),
        0U,
        {},
        {});
}

LemmaFactoryNode RecursiveLemmaFactory::solve_impl(
    FormalizationProposal proposal,
    std::size_t depth,
    const std::vector<std::string>& inherited_context,
    const std::unordered_set<std::string>& ancestors) {
    validate_formalization_proposal(proposal);
    const std::string fingerprint = proposal_fingerprint(proposal);

    if (ancestors.contains(fingerprint)) {
        return LemmaFactoryNode{
            .proposal = std::move(proposal),
            .depth = depth,
            .status = "cycle",
            .initial_result = std::nullopt,
            .children = {},
            .retry_result = std::nullopt,
            .note = "proposal already exists on the active recursion path",
        };
    }

    if (remaining_nodes_ == 0U) {
        return LemmaFactoryNode{
            .proposal = std::move(proposal),
            .depth = depth,
            .status = "node_budget",
            .initial_result = std::nullopt,
            .children = {},
            .retry_result = std::nullopt,
            .note = "recursive lemma factory node budget exhausted",
        };
    }

    --remaining_nodes_;

    auto initial = formalize(
        proposal,
        searcher_,
        inherited_context);

    if (initial.proven()) {
        return LemmaFactoryNode{
            .proposal = std::move(proposal),
            .depth = depth,
            .status = "proven",
            .initial_result = std::move(initial),
        };
    }

    if (depth >= config_.max_depth) {
        return LemmaFactoryNode{
            .proposal = std::move(proposal),
            .depth = depth,
            .status = "depth_limit",
            .initial_result = std::move(initial),
            .children = {},
            .retry_result = std::nullopt,
            .note = "maximum recursive lemma depth reached",
        };
    }

    auto children_raw =
        decomposer_.decompose(proposal, initial);
    if (children_raw.size() > config_.max_children) {
        children_raw.resize(config_.max_children);
    }

    std::vector<LemmaFactoryNode> child_nodes;
    std::vector<std::string> retry_context = inherited_context;

    auto next_ancestors = ancestors;
    next_ancestors.insert(fingerprint);

    for (auto& child_proposal : children_raw) {
        auto child = solve_impl(
            std::move(child_proposal),
            depth + 1U,
            retry_context,
            next_ancestors);

        if (child.proven()) {
            append_unique(
                retry_context,
                child.proof_declarations());
        }

        child_nodes.push_back(std::move(child));
    }

    if (child_nodes.empty()) {
        return LemmaFactoryNode{
            .proposal = std::move(proposal),
            .depth = depth,
            .status = "undecomposed_failure",
            .initial_result = std::move(initial),
            .children = {},
            .retry_result = std::nullopt,
            .note = "decomposer produced no child lemmas",
        };
    }

    auto retry = formalize(
        proposal,
        searcher_,
        retry_context);

    const bool retry_proven = retry.proven();
    return LemmaFactoryNode{
        .proposal = std::move(proposal),
        .depth = depth,
        .status = retry_proven
            ? "proven_after_children"
            : "children_insufficient",
        .initial_result = std::move(initial),
        .children = std::move(child_nodes),
        .retry_result = std::move(retry),
    };
}

std::string decomposition_prompt(
    const FormalizationProposal& proposal_input,
    const FormalizationResult& failed_result,
    std::size_t max_children) {
    auto proposal = proposal_input;
    validate_formalization_proposal(proposal);

    std::ostringstream out;
    out
        << "A Lean theorem candidate failed deterministic proof search.\n"
        << "Propose 0 to " << max_children
        << " smaller helper lemmas that could make the target easier.\n"
        << "Return JSON only as an object with key \"lemmas\". "
        << "Each lemma must contain exactly the proposal fields: "
        << "name, namespace, binders, proposition, imports, domain, rationale.\n"
        << "Do not provide proofs. Do not use sorry, admit, axiom, unsafe, "
        << "set_option, or Lean commands. Avoid restating the target.\n\n"
        << "Target qualified name: " << proposal.qualified_name() << "\n"
        << "Target proposition: " << proposal.proposition << "\n"
        << "Domain: " << proposal.domain << "\n"
        << "Failed attempts:\n";

    for (const auto& attempt : failed_result.search.attempts) {
        const std::string excerpt =
            attempt.output.size() <= 1200U
                ? attempt.output
                : attempt.output.substr(attempt.output.size() - 1200U);
        out
            << "- tactic: " << attempt.tactic
            << "; exit_code: " << attempt.exit_code
            << "; compiler_excerpt: " << excerpt << "\n";
    }

    return out.str();
}

std::vector<FormalizationProposal> parse_decomposition_json(
    std::string_view text,
    std::size_t max_children) {
    if (max_children == 0U) {
        throw std::invalid_argument("max_children must be positive");
    }

    const std::string json(text);
    const auto keys = top_level_keys(json);
    if (keys != std::set<std::string>{"lemmas"}) {
        throw std::invalid_argument(
            "decomposition must be an object containing only lemmas");
    }

    const auto lemmas = json_util::object_array(json, "lemmas");
    if (lemmas.size() > max_children) {
        throw std::invalid_argument(
            "decomposition exceeds max_children");
    }

    std::vector<FormalizationProposal> proposals;
    std::unordered_set<std::string> qualified_names;

    for (const auto& object : lemmas) {
        auto proposal = proposal_from_json_object(object);
        const auto name = proposal.qualified_name();
        if (!qualified_names.insert(name).second) {
            throw std::invalid_argument(
                "duplicate helper lemma names are forbidden");
        }
        proposals.push_back(std::move(proposal));
    }

    return proposals;
}

} // namespace expert_robot
