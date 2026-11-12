#include "expert_robot/math/mmir.hpp"

#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>
#include <utility>

namespace expert_robot::mmir {
namespace {

std::string glyph_key(std::string_view name_space, std::string_view glyph) {
    return std::string(name_space) + "::" + std::string(glyph);
}

bool valid_math_type(const MathType& type) noexcept {
    return !type.name.empty() && std::isfinite(type.scale_to_si) &&
        type.scale_to_si > 0.0L;
}

bool same_dimensions(const MathType& lhs, const MathType& rhs) noexcept {
    return lhs.dimensions == rhs.dimensions;
}

namespace {

int checked_dimension(int lhs, int rhs, bool subtract) {
    const auto result = subtract
        ? static_cast<long long>(lhs) - static_cast<long long>(rhs)
        : static_cast<long long>(lhs) + static_cast<long long>(rhs);
    if (result < std::numeric_limits<int>::min() ||
        result > std::numeric_limits<int>::max()) {
        throw std::overflow_error("SI dimension exponent overflow");
    }
    return static_cast<int>(result);
}

void require_valid_type(const MathType& type) {
    if (!valid_math_type(type)) {
        throw std::invalid_argument("mathematical type requires a name and positive finite SI scale");
    }
}

std::string unit_product(const MathType& lhs, const MathType& rhs, char operation) {
    const auto left = lhs.unit_symbol.empty() ? "1" : lhs.unit_symbol;
    const auto right = rhs.unit_symbol.empty() ? "1" : rhs.unit_symbol;
    return "(" + left + ")" + operation + "(" + right + ")";
}

} // namespace

MathType multiply_types(const MathType& lhs, const MathType& rhs) {
    require_valid_type(lhs);
    require_valid_type(rhs);
    MathType result;
    result.name = lhs.name + "*" + rhs.name;
    result.unit_symbol = unit_product(lhs, rhs, '*');
    result.scale_to_si = lhs.scale_to_si * rhs.scale_to_si;
    for (std::size_t i = 0; i < dimension_count; ++i) {
        result.dimensions[i] = checked_dimension(lhs.dimensions[i], rhs.dimensions[i], false);
    }
    require_valid_type(result);
    return result;
}

MathType divide_types(const MathType& lhs, const MathType& rhs) {
    require_valid_type(lhs);
    require_valid_type(rhs);
    MathType result;
    result.name = lhs.name + "/" + rhs.name;
    result.unit_symbol = unit_product(lhs, rhs, '/');
    result.scale_to_si = lhs.scale_to_si / rhs.scale_to_si;
    for (std::size_t i = 0; i < dimension_count; ++i) {
        result.dimensions[i] = checked_dimension(lhs.dimensions[i], rhs.dimensions[i], true);
    }
    require_valid_type(result);
    return result;
}

MathType integer_power(const MathType& base, int exponent) {
    require_valid_type(base);
    MathType result;
    result.name = base.name + "^" + std::to_string(exponent);
    result.unit_symbol = "(" + base.unit_symbol + ")^" + std::to_string(exponent);
    result.scale_to_si = std::pow(base.scale_to_si, exponent);
    for (std::size_t i = 0; i < dimension_count; ++i) {
        const auto value = static_cast<long long>(base.dimensions[i]) *
            static_cast<long long>(exponent);
        if (value < std::numeric_limits<int>::min() ||
            value > std::numeric_limits<int>::max()) {
            throw std::overflow_error("SI dimension exponent overflow");
        }
        result.dimensions[i] = static_cast<int>(value);
    }
    require_valid_type(result);
    return result;
}

long double convert_value(long double value, const MathType& from, const MathType& to) {
    require_valid_type(from);
    require_valid_type(to);
    if (!std::isfinite(value)) {
        throw std::invalid_argument("unit conversion requires a finite value");
    }
    if (!same_dimensions(from, to)) {
        throw std::invalid_argument("cannot convert between dimensionally incompatible units");
    }
    const auto converted = value * from.scale_to_si / to.scale_to_si;
    if (!std::isfinite(converted)) {
        throw std::overflow_error("unit conversion result is not finite");
    }
    return converted;
}

void OperatorRegistry::add(OperatorSpec spec) {
    if (spec.id.empty() || spec.name_space.empty() || spec.glyph.empty() ||
        spec.output_type.empty() || spec.semantic_definition.empty()) {
        throw std::invalid_argument("operator identity, glyph, output type, and semantics are required");
    }
    if (spec.min_arity == 0 || spec.min_arity > spec.max_arity) {
        throw std::invalid_argument("operator arity must have a positive minimum not exceeding its maximum");
    }
    // One input type denotes a homogeneous operator of any declared arity.
    // Otherwise, the signature must specify one type for every possible slot.
    if (spec.input_types.empty() ||
        (spec.input_types.size() != 1 && spec.input_types.size() != spec.max_arity)) {
        throw std::invalid_argument("input signature must be homogeneous (one type) or positional (max_arity types)");
    }
    if (spec.verification_status != "specified" &&
        spec.verification_status != "conjectural" &&
        spec.verification_status != "unqualified") {
        throw std::invalid_argument("verification_status must be specified, conjectural, or unqualified");
    }
    if (by_id_.contains(spec.id)) {
        throw std::invalid_argument("duplicate operator id: " + spec.id);
    }
    const auto key = glyph_key(spec.name_space, spec.glyph);
    if (glyph_to_id_.contains(key)) {
        throw std::invalid_argument("duplicate glyph in semantic namespace: " + key);
    }
    glyph_to_id_.emplace(key, spec.id);
    by_id_.emplace(spec.id, std::move(spec));
}

const OperatorSpec* OperatorRegistry::find(std::string_view id) const {
    const auto it = by_id_.find(std::string(id));
    return it == by_id_.end() ? nullptr : &it->second;
}

const OperatorSpec* OperatorRegistry::resolve(
    std::string_view name_space, std::string_view glyph) const {
    const auto it = glyph_to_id_.find(glyph_key(name_space, glyph));
    return it == glyph_to_id_.end() ? nullptr : find(it->second);
}

void ExpressionGraph::add(ExpressionNode node) {
    if (node.id.empty() || node.type.empty()) {
        throw std::invalid_argument("expression node id and type are required");
    }
    if (nodes_.contains(node.id)) {
        throw std::invalid_argument("duplicate expression node id: " + node.id);
    }
    nodes_.emplace(node.id, std::move(node));
}

const ExpressionNode* ExpressionGraph::find(std::string_view id) const {
    const auto it = nodes_.find(std::string(id));
    return it == nodes_.end() ? nullptr : &it->second;
}

std::vector<ValidationIssue> ExpressionGraph::validate(
    const OperatorRegistry& registry) const {
    std::vector<ValidationIssue> issues;
    for (const auto& [id, node] : nodes_) {
        if (node.kind != NodeKind::application) {
            if (!node.operator_id.empty() || !node.operands.empty()) {
                issues.push_back({id, "NON_APPLICATION_HAS_OPERATOR",
                    "only application nodes may declare an operator or operands"});
            }
            continue;
        }

        const auto* op = registry.find(node.operator_id);
        if (op == nullptr) {
            issues.push_back({id, "UNKNOWN_OPERATOR",
                "application references an unregistered operator"});
            continue;
        }
        if (node.operands.size() < op->min_arity ||
            node.operands.size() > op->max_arity) {
            issues.push_back({id, "ARITY_MISMATCH",
                "operand count is outside the operator's declared arity"});
        }
        if (node.type != op->output_type) {
            issues.push_back({id, "OUTPUT_TYPE_MISMATCH",
                "application result type differs from the operator output type"});
        }
        for (std::size_t index = 0; index < node.operands.size(); ++index) {
            const auto& operand_id = node.operands[index];
            const auto* operand = find(operand_id);
            if (operand == nullptr) {
                issues.push_back({id, "MISSING_OPERAND",
                    "application references missing operand: " + operand_id});
                continue;
            }
            const auto expected_index = index < op->input_types.size()
                ? index : op->input_types.size() - 1;
            if (operand->type != op->input_types[expected_index]) {
                issues.push_back({id, "INPUT_TYPE_MISMATCH",
                    "operand " + operand_id + " has type " + operand->type +
                    "; expected " + op->input_types[expected_index]});
            }
        }
    }

    // The core expression graph is acyclic. Feedback and recursion must be
    // represented by explicit typed nodes in a later extension, never by
    // silently accepting arbitrary cycles.
    enum class Mark { unseen, visiting, complete };
    std::unordered_map<std::string, Mark> marks;
    std::function<void(const std::string&)> visit = [&](const std::string& id) {
        auto& mark = marks[id];
        if (mark == Mark::complete) return;
        if (mark == Mark::visiting) {
            issues.push_back({id, "IMPLICIT_CYCLE",
                "expression dependency cycle requires an explicit feedback construct"});
            return;
        }
        mark = Mark::visiting;
        const auto* node = find(id);
        if (node != nullptr) {
            for (const auto& child : node->operands) {
                if (find(child) != nullptr) visit(child);
            }
        }
        mark = Mark::complete;
    };
    for (const auto& [id, unused] : nodes_) {
        (void)unused;
        if (marks[id] == Mark::unseen) visit(id);
    }
    return issues;
}

} // namespace expert_robot::mmir
