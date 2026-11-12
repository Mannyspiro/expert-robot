#include "expert_robot/math/mmir.hpp"

#include <cassert>
#include <stdexcept>

int main() {
    using namespace expert_robot::mmir;

    OperatorRegistry registry;
    registry.add({
        .id = "xa.arithmetic.add",
        .name_space = "xa.arithmetic",
        .glyph = "+",
        .min_arity = 2,
        .max_arity = 2,
        .input_types = {"Real"},
        .output_type = "Real",
        .associative = true,
        .commutative = true,
        .has_identity = true,
        .semantic_definition = "Addition over real numbers",
    });
    registry.add({
        .id = "xa.harmonic.couple",
        .name_space = "xa.harmonic",
        .glyph = "⋈",
        .min_arity = 2,
        .max_arity = 8,
        .input_types = {"Oscillator"},
        .output_type = "CoupledSystem",
        .semantic_definition = "Construct a coupled oscillator system",
    });

    assert(registry.size() == 2);
    assert(registry.resolve("xa.arithmetic", "+") != nullptr);
    assert(registry.resolve("xa.harmonic", "⋈") != nullptr);
    assert(registry.resolve("xa.arithmetic", "⋈") == nullptr);

    ExpressionGraph graph;
    graph.add({.id = "x", .kind = NodeKind::variable, .type = "Real", .symbol = "x"});
    graph.add({.id = "y", .kind = NodeKind::variable, .type = "Real", .symbol = "y"});
    graph.add({
        .id = "sum", .kind = NodeKind::application, .type = "Real",
        .operator_id = "xa.arithmetic.add", .operands = {"x", "y"},
    });
    assert(graph.validate(registry).empty());

    ExpressionGraph bad_arity;
    bad_arity.add({.id = "x", .kind = NodeKind::variable, .type = "Real"});
    bad_arity.add({
        .id = "sum", .kind = NodeKind::application, .type = "Real",
        .operator_id = "xa.arithmetic.add", .operands = {"x"},
    });
    const auto arity_issues = bad_arity.validate(registry);
    assert(!arity_issues.empty());
    assert(arity_issues.front().code == "ARITY_MISMATCH");

    ExpressionGraph bad_type;
    bad_type.add({.id = "x", .kind = NodeKind::variable, .type = "Complex"});
    bad_type.add({.id = "y", .kind = NodeKind::variable, .type = "Real"});
    bad_type.add({
        .id = "sum", .kind = NodeKind::application, .type = "Real",
        .operator_id = "xa.arithmetic.add", .operands = {"x", "y"},
    });
    const auto type_issues = bad_type.validate(registry);
    bool found_type_error = false;
    for (const auto& issue : type_issues) {
        if (issue.code == "INPUT_TYPE_MISMATCH") found_type_error = true;
    }
    assert(found_type_error);

    bool duplicate_glyph_rejected = false;
    try {
        registry.add({
            .id = "xa.arithmetic.other",
            .name_space = "xa.arithmetic",
            .glyph = "+",
            .min_arity = 2,
            .max_arity = 2,
            .input_types = {"Real"},
            .output_type = "Real",
            .semantic_definition = "Ambiguous duplicate",
        });
    } catch (const std::invalid_argument&) {
        duplicate_glyph_rejected = true;
    }
    assert(duplicate_glyph_rejected);

    bool malformed_signature_rejected = false;
    try {
        registry.add({
            .id = "xa.arithmetic.bad_signature",
            .name_space = "xa.arithmetic",
            .glyph = "⊞",
            .min_arity = 2,
            .max_arity = 3,
            .input_types = {"Real", "Complex"},
            .output_type = "Real",
            .semantic_definition = "Invalid incomplete positional signature",
        });
    } catch (const std::invalid_argument&) {
        malformed_signature_rejected = true;
    }
    assert(malformed_signature_rejected);

    ExpressionGraph missing_operand;
    missing_operand.add({
        .id = "sum", .kind = NodeKind::application, .type = "Real",
        .operator_id = "xa.arithmetic.add", .operands = {"absent", "also_absent"},
    });
    const auto missing_issues = missing_operand.validate(registry);
    bool found_missing = false;
    for (const auto& issue : missing_issues) {
        if (issue.code == "MISSING_OPERAND") found_missing = true;
    }
    assert(found_missing);

    ExpressionGraph implicit_cycle;
    implicit_cycle.add({
        .id = "loop", .kind = NodeKind::application, .type = "Real",
        .operator_id = "xa.arithmetic.add", .operands = {"loop", "loop"},
    });
    const auto cycle_issues = implicit_cycle.validate(registry);
    bool found_cycle = false;
    for (const auto& issue : cycle_issues) {
        if (issue.code == "IMPLICIT_CYCLE") found_cycle = true;
    }
    assert(found_cycle);

    bool invalid_status_rejected = false;
    try {
        registry.add({
            .id = "xa.arithmetic.unearned_proof",
            .name_space = "xa.arithmetic",
            .glyph = "⊕",
            .min_arity = 2,
            .max_arity = 2,
            .input_types = {"Real"},
            .output_type = "Real",
            .semantic_definition = "Cannot self-assert a proof receipt",
            .verification_status = "formally_verified",
        });
    } catch (const std::invalid_argument&) {
        invalid_status_rejected = true;
    }
    assert(invalid_status_rejected);

    return 0;
}
