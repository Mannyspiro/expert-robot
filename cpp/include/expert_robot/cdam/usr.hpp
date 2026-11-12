#pragma once

#include <array>
#include <cstddef>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace expert_robot::cdam {

enum class NodeKind {
    Variable,
    Component,
    Operator,
    Constraint,
    Boundary,
    Storage
};

enum class UnitStatus {
    Unchecked,
    Consistent,
    Inconsistent
};

struct Dimension {
    // SI base exponents: kg, m, s, A, K, mol, cd.
    std::array<int, 7> exponents{};
};

struct SystemNode {
    std::string id;
    std::string label;       // Domain-specific wording; never used as proof.
    NodeKind kind{NodeKind::Variable};
    Dimension dimension{};
};

struct SystemEdge {
    std::string source;
    std::string relation;
    std::string target;
};

struct UniversalSystemRepresentation {
    std::string system_id;
    std::string domain;
    std::vector<SystemNode> nodes;
    std::vector<SystemEdge> edges;
    std::set<std::string> invariant_ids;
    std::vector<std::string> assumptions;
    std::string validity_regime;
    UnitStatus unit_status{UnitStatus::Unchecked};
};

inline void validate_usr(const UniversalSystemRepresentation& system) {
    if (system.system_id.empty() || system.domain.empty()) {
        throw std::invalid_argument("USR system_id and domain must be non-empty");
    }
    if (system.nodes.empty()) {
        throw std::invalid_argument("USR must contain at least one node");
    }

    std::unordered_set<std::string> ids;
    for (const auto& node : system.nodes) {
        if (node.id.empty() || node.label.empty()) {
            throw std::invalid_argument("USR node id and label must be non-empty");
        }
        if (!ids.insert(node.id).second) {
            throw std::invalid_argument("USR node ids must be unique");
        }
        for (const int exponent : node.dimension.exponents) {
            if (exponent < -16 || exponent > 16) {
                throw std::invalid_argument("USR dimension exponent is outside [-16, 16]");
            }
        }
    }

    std::set<std::tuple<std::string, std::string, std::string>> edges;
    for (const auto& edge : system.edges) {
        if (!ids.contains(edge.source) || !ids.contains(edge.target) ||
            edge.relation.empty()) {
            throw std::invalid_argument("USR edge has an unknown endpoint or empty relation");
        }
        if (!edges.emplace(edge.source, edge.relation, edge.target).second) {
            throw std::invalid_argument("USR contains a duplicate edge");
        }
    }

    for (const auto& invariant : system.invariant_ids) {
        if (invariant.empty()) {
            throw std::invalid_argument("USR invariant identifiers must be non-empty");
        }
    }
}

} // namespace expert_robot::cdam
