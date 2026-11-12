#pragma once

#include <array>
#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

namespace expert_robot::mmir {

inline constexpr std::size_t dimension_count = 7;

struct MathType {
    std::string name;
    // SI base-dimension exponents: length, mass, time, current,
    // temperature, amount, luminous intensity.
    std::array<int, dimension_count> dimensions{};
    std::string unit_symbol;
    // Positive multiplicative conversion factor from this unit to SI.
    // Affine units (for example Celsius) are deliberately not represented yet.
    long double scale_to_si{1.0L};
};

[[nodiscard]] bool valid_math_type(const MathType& type) noexcept;
[[nodiscard]] bool same_dimensions(const MathType& lhs, const MathType& rhs) noexcept;
[[nodiscard]] MathType multiply_types(const MathType& lhs, const MathType& rhs);
[[nodiscard]] MathType divide_types(const MathType& lhs, const MathType& rhs);
[[nodiscard]] MathType integer_power(const MathType& base, int exponent);
[[nodiscard]] long double convert_value(
    long double value, const MathType& from, const MathType& to);

struct OperatorSpec {
    std::string id;
    std::string name_space;
    std::string glyph;
    std::size_t min_arity{0};
    std::size_t max_arity{0};
    std::vector<std::string> input_types;
    std::string output_type;
    bool associative{false};
    bool commutative{false};
    bool has_identity{false};
    bool has_inverse{false};
    bool distributive{false};
    std::string semantic_definition;
    std::string verification_status{"specified"};
};

class OperatorRegistry {
public:
    void add(OperatorSpec spec);
    [[nodiscard]] const OperatorSpec* find(std::string_view id) const;
    [[nodiscard]] const OperatorSpec* resolve(
        std::string_view name_space, std::string_view glyph) const;
    [[nodiscard]] std::size_t size() const noexcept { return by_id_.size(); }

private:
    std::unordered_map<std::string, OperatorSpec> by_id_;
    std::unordered_map<std::string, std::string> glyph_to_id_;
};

enum class NodeKind {
    variable,
    constant,
    application,
    coordinate_frame,
    transformation,
    tensor,
    relation,
    spectrum,
    flow
};

struct ExpressionNode {
    std::string id;
    NodeKind kind{NodeKind::variable};
    std::string type;
    std::string symbol;
    std::string operator_id;
    std::vector<std::string> operands;
    std::vector<std::string> assumptions;
    std::string provenance;
};

struct ValidationIssue {
    std::string node_id;
    std::string code;
    std::string message;
};

class ExpressionGraph {
public:
    void add(ExpressionNode node);
    [[nodiscard]] const ExpressionNode* find(std::string_view id) const;
    [[nodiscard]] std::vector<ValidationIssue> validate(
        const OperatorRegistry& registry) const;
    [[nodiscard]] std::size_t size() const noexcept { return nodes_.size(); }

private:
    std::unordered_map<std::string, ExpressionNode> nodes_;
};

} // namespace expert_robot::mmir
