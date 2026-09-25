#include "expert_robot/research/knowledge_consolidator.hpp"

#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace expert_robot::research {
namespace {

void add_unique(
    std::vector<std::string>& values,
    std::string value) {
    if (std::find(
            values.begin(),
            values.end(),
            value) == values.end()) {
        values.push_back(
            std::move(value));
    }
}

} // namespace

VerifiedKnowledgeConsolidator::VerifiedKnowledgeConsolidator(
    KnowledgeGraph& graph,
    ResearchEpisodeLedger* episode_ledger,
    std::filesystem::path persistence_path)
    : graph_(graph),
      episode_ledger_(episode_ledger),
      persistence_path_(
          std::move(persistence_path)) {}

ConsolidationResult
VerifiedKnowledgeConsolidator::consolidate(
    std::string_view episode_id,
    std::string_view target_theorem,
    const CandidateVerification& candidate) {
    if (episode_id.empty()) {
        throw std::invalid_argument(
            "knowledge consolidation requires episode_id");
    }

    if (!candidate.proven() ||
        !candidate.proposal.has_value() ||
        !candidate.formalization.has_value() ||
        !candidate.formalization->
            lean_declaration.has_value()) {
        throw std::invalid_argument(
            "only proof-accepted candidates can be consolidated");
    }

    const auto& proposal =
        *candidate.proposal;
    const std::string theorem_name =
        proposal.qualified_name();
    const std::string statement =
        proposal.statement();

    bool created = false;
    bool upgraded = false;

    try {
        const auto& existing =
            graph_.get(
                theorem_name);

        if (!existing.statement.empty() &&
            existing.statement != statement) {
            throw std::logic_error(
                "verified theorem name conflicts with existing graph statement");
        }

        TheoremNode updated =
            existing;

        if (updated.status != "verified") {
            updated.status = "verified";
            upgraded = true;
        }

        if (updated.statement.empty()) {
            updated.statement = statement;
            upgraded = true;
        }

        if (updated.domain == "unknown" &&
            proposal.domain != "unknown") {
            updated.domain =
                proposal.domain;
            upgraded = true;
        }

        add_unique(
            updated.tags,
            "lean_verified");
        add_unique(
            updated.tags,
            "generated");

        graph_.upsert_node(
            std::move(updated));
    } catch (const std::out_of_range&) {
        graph_.add_node(
            TheoremNode{
                .name = theorem_name,
                .source =
                    "generated:" +
                    std::string(episode_id),
                .status = "verified",
                .statement = statement,
                .domain = proposal.domain,
                .tags = {
                    "generated",
                    "lean_verified"
                },
            });
        created = true;
    }

    bool linked = false;
    if (!target_theorem.empty() &&
        target_theorem != theorem_name) {
        try {
            (void)graph_.get(
                target_theorem);

            graph_.add_edge(
                TheoremEdge{
                    .source =
                        std::string(
                            target_theorem),
                    .relation = "USES",
                    .target =
                        theorem_name,
                });
            linked = true;
        } catch (const std::out_of_range&) {
            // The verified theorem is still retained even if the caller's
            // target identifier is not present in this graph snapshot.
        }
    }

    if (!persistence_path_.empty()) {
        graph_.save(
            persistence_path_);
    }

    std::string event_hash;
    if (episode_ledger_ != nullptr) {
        const std::string proof_hash =
            sha256_hex(
                *candidate.formalization->
                    lean_declaration);

        std::ostringstream payload;
        payload
            << "theorem=" << theorem_name << "\n"
            << "target=" << target_theorem << "\n"
            << "statement_sha256="
            << sha256_hex(statement) << "\n"
            << "proof_declaration_sha256="
            << proof_hash << "\n"
            << "node_created="
            << (created ? "true" : "false")
            << "\n"
            << "node_upgraded="
            << (upgraded ? "true" : "false")
            << "\n"
            << "linked_to_target="
            << (linked ? "true" : "false")
            << "\n";

        const auto event =
            episode_ledger_->append(
                episode_id,
                "verified_knowledge_consolidated",
                payload.str());

        event_hash =
            event.event_hash;
    }

    return ConsolidationResult{
        .theorem_name =
            theorem_name,
        .node_created =
            created,
        .node_upgraded =
            upgraded,
        .linked_to_target =
            linked,
        .episode_event_hash =
            std::move(event_hash),
    };
}

} // namespace expert_robot::research
