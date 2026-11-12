#pragma once

#include "expert_robot/cdam/usr.hpp"

#include <algorithm>
#include <map>
#include <numeric>
#include <string>
#include <utility>
#include <vector>

namespace expert_robot::cdam {

enum class MappingClass {
    NoMatch,
    InducedSubgraphEmbedding,
    StructuralIsomorphism
};

inline const char* mapping_class_name(MappingClass value) noexcept {
    switch (value) {
        case MappingClass::NoMatch: return "no_match";
        case MappingClass::InducedSubgraphEmbedding: return "induced_subgraph_embedding";
        case MappingClass::StructuralIsomorphism: return "structural_isomorphism";
    }
    return "unknown";
}

struct MappingResult {
    std::string source_system_id;
    std::string target_system_id;
    MappingClass mapping_class{MappingClass::NoMatch};
    std::map<std::string, std::string> node_mapping;
    double node_coverage{0.0};
    double edge_coverage{0.0};
    double invariant_coverage{0.0};
    std::vector<std::string> preserved_invariants;
    std::vector<std::string> unmatched_source_edges;
    UnitStatus source_unit_status{UnitStatus::Unchecked};
    UnitStatus target_unit_status{UnitStatus::Unchecked};
    std::vector<std::string> caveats;
};

struct MatcherLimits {
    std::size_t max_search_states{100000};
};

namespace detail {

inline std::size_t in_degree(const UniversalSystemRepresentation& s,
                             const std::string& id) {
    return static_cast<std::size_t>(std::count_if(
        s.edges.begin(), s.edges.end(),
        [&](const SystemEdge& e) { return e.target == id; }));
}

inline std::size_t out_degree(const UniversalSystemRepresentation& s,
                              const std::string& id) {
    return static_cast<std::size_t>(std::count_if(
        s.edges.begin(), s.edges.end(),
        [&](const SystemEdge& e) { return e.source == id; }));
}

inline bool has_edge(const UniversalSystemRepresentation& s,
                     const std::string& from,
                     const std::string& relation,
                     const std::string& to) {
    return std::any_of(s.edges.begin(), s.edges.end(),
        [&](const SystemEdge& e) {
            return e.source == from && e.relation == relation && e.target == to;
        });
}

inline std::vector<std::string> relations_between(
    const UniversalSystemRepresentation& s,
    const std::string& from,
    const std::string& to) {
    std::vector<std::string> result;
    for (const auto& e : s.edges) {
        if (e.source == from && e.target == to) result.push_back(e.relation);
    }
    std::sort(result.begin(), result.end());
    return result;
}

inline bool same_local_signature(const UniversalSystemRepresentation& a,
                                 const SystemNode& an,
                                 const UniversalSystemRepresentation& b,
                                 const SystemNode& bn) {
    return an.kind == bn.kind &&
           in_degree(a, an.id) == in_degree(b, bn.id) &&
           out_degree(a, an.id) == out_degree(b, bn.id);
}

} // namespace detail

class StructuralMatcher {
public:
    explicit StructuralMatcher(MatcherLimits limits = {}) : limits_(limits) {
        if (limits_.max_search_states == 0) {
            throw std::invalid_argument("max_search_states must be positive");
        }
    }

    [[nodiscard]] MappingResult match(
        const UniversalSystemRepresentation& source,
        const UniversalSystemRepresentation& target) const {
        validate_usr(source);
        validate_usr(target);

        MappingResult result;
        result.source_system_id = source.system_id;
        result.target_system_id = target.system_id;
        result.source_unit_status = source.unit_status;
        result.target_unit_status = target.unit_status;

        if (source.nodes.size() > target.nodes.size() ||
            source.edges.size() > target.edges.size()) {
            result.caveats.emplace_back("Target representation is smaller than source");
            return result;
        }

        std::vector<const SystemNode*> ordered;
        ordered.reserve(source.nodes.size());
        for (const auto& n : source.nodes) ordered.push_back(&n);

        std::sort(ordered.begin(), ordered.end(), [&](const auto* a, const auto* b) {
            const auto da = detail::in_degree(source, a->id) +
                            detail::out_degree(source, a->id);
            const auto db = detail::in_degree(source, b->id) +
                            detail::out_degree(source, b->id);
            if (da != db) return da > db;
            return a->id < b->id;
        });

        std::map<std::string, std::string> mapping;
        std::set<std::string> used_targets;
        std::size_t states = 0;
        bool found = false;

        const auto search = [&](const auto& self, std::size_t index) -> void {
            if (found || states >= limits_.max_search_states) return;
            ++states;
            if (index == ordered.size()) {
                found = true;
                return;
            }

            const auto& current = *ordered[index];
            for (const auto& candidate : target.nodes) {
                if (used_targets.contains(candidate.id) ||
                    !detail::same_local_signature(source, current, target, candidate)) {
                    continue;
                }

                bool compatible = true;
                for (const auto& [mapped_source, mapped_target] : mapping) {
                    const auto source_relations =
                        detail::relations_between(source, current.id, mapped_source);
                    const auto target_relations =
                        detail::relations_between(target, candidate.id, mapped_target);
                    const auto source_reverse =
                        detail::relations_between(source, mapped_source, current.id);
                    const auto target_reverse =
                        detail::relations_between(target, mapped_target, candidate.id);
                    if (source_relations != target_relations ||
                        source_reverse != target_reverse) {
                        compatible = false;
                        break;
                    }
                }
                if (!compatible) continue;

                mapping.emplace(current.id, candidate.id);
                used_targets.insert(candidate.id);
                self(self, index + 1);
                if (found) return;
                used_targets.erase(candidate.id);
                mapping.erase(current.id);
            }
        };

        search(search, 0);
        if (!found) {
            result.caveats.emplace_back(
                states >= limits_.max_search_states
                    ? "Search-state budget exhausted; absence of a mapping is inconclusive"
                    : "No structure-preserving node mapping was found");
            return result;
        }

        result.node_mapping = mapping;
        result.node_coverage = static_cast<double>(mapping.size()) /
                              static_cast<double>(source.nodes.size());

        std::size_t matched_edges = 0;
        for (const auto& edge : source.edges) {
            const auto from = mapping.at(edge.source);
            const auto to = mapping.at(edge.target);
            if (detail::has_edge(target, from, edge.relation, to)) {
                ++matched_edges;
            } else {
                result.unmatched_source_edges.push_back(
                    edge.source + " -" + edge.relation + "-> " + edge.target);
            }
        }
        result.edge_coverage = source.edges.empty()
            ? 1.0
            : static_cast<double>(matched_edges) /
              static_cast<double>(source.edges.size());

        for (const auto& invariant : source.invariant_ids) {
            if (target.invariant_ids.contains(invariant)) {
                result.preserved_invariants.push_back(invariant);
            }
        }
        result.invariant_coverage = source.invariant_ids.empty()
            ? 1.0
            : static_cast<double>(result.preserved_invariants.size()) /
              static_cast<double>(source.invariant_ids.size());

        const bool equal_node_count = source.nodes.size() == target.nodes.size();
        const bool equal_edge_count = source.edges.size() == target.edges.size();
        result.mapping_class = equal_node_count && equal_edge_count
            ? MappingClass::StructuralIsomorphism
            : MappingClass::InducedSubgraphEmbedding;

        if (source.unit_status == UnitStatus::Inconsistent ||
            target.unit_status == UnitStatus::Inconsistent) {
            result.caveats.emplace_back(
                "At least one representation has failed dimensional validation");
        } else if (source.unit_status == UnitStatus::Unchecked ||
                   target.unit_status == UnitStatus::Unchecked) {
            result.caveats.emplace_back(
                "Dimensional validation is incomplete; structural match is not physical validation");
        }

        result.caveats.emplace_back(
            "Structural matching is a candidate correspondence, not proof of physical or mathematical equivalence");
        return result;
    }

private:
    MatcherLimits limits_;
};

} // namespace expert_robot::cdam
