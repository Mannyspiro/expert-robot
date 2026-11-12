#include "expert_robot/cdam/invariant_library.hpp"
#include "expert_robot/cdam/structural_matcher.hpp"

#include <cassert>
#include <stdexcept>
#include <string>

using expert_robot::cdam::Dimension;
using expert_robot::cdam::InvariantLibrary;
using expert_robot::cdam::MappingClass;
using expert_robot::cdam::NodeKind;
using expert_robot::cdam::StructuralMatcher;
using expert_robot::cdam::SystemEdge;
using expert_robot::cdam::SystemNode;
using expert_robot::cdam::UnitStatus;
using expert_robot::cdam::UniversalSystemRepresentation;

namespace {

UniversalSystemRepresentation electrical_network() {
    return {
        .system_id = "electrical.simple_series",
        .domain = "electrical_networks",
        .nodes = {
            {"battery", "Battery", NodeKind::Component, Dimension{{0,0,0,0,0,0,0}}},
            {"voltage", "Voltage", NodeKind::Variable, Dimension{{1,2,-3,-1,0,0,0}}},
            {"current", "Current", NodeKind::Variable, Dimension{{0,0,0,1,0,0,0}}},
            {"resistor", "Resistor", NodeKind::Component, Dimension{{1,2,-3,-2,0,0,0}}}
        },
        .edges = {
            {"battery", "imposes_effort", "voltage"},
            {"voltage", "drives_flow", "current"},
            {"current", "passes_through", "resistor"}
        },
        .invariant_ids = {"invariant.network.node_balance"},
        .assumptions = {"lumped-element approximation"},
        .validity_regime = "linear, time-invariant operating point",
        .unit_status = UnitStatus::Consistent
    };
}

UniversalSystemRepresentation hydraulic_network() {
    return {
        .system_id = "hydraulic.simple_pipe",
        .domain = "fluid_networks",
        .nodes = {
            {"pump", "Pump", NodeKind::Component, Dimension{{0,0,0,0,0,0,0}}},
            {"pressure", "Pressure", NodeKind::Variable, Dimension{{1,-1,-2,0,0,0,0}}},
            {"flow", "Volumetric flow", NodeKind::Variable, Dimension{{0,3,-1,0,0,0,0}}},
            {"pipe", "Pipe", NodeKind::Component, Dimension{{0,0,0,0,0,0,0}}}
        },
        .edges = {
            {"pump", "imposes_effort", "pressure"},
            {"pressure", "drives_flow", "flow"},
            {"flow", "passes_through", "pipe"}
        },
        .invariant_ids = {"invariant.network.node_balance"},
        .assumptions = {"lumped hydraulic approximation"},
        .validity_regime = "laminar flow under declared geometry and fluid properties",
        .unit_status = UnitStatus::Consistent
    };
}

} // namespace

int main() {
    const auto electrical = electrical_network();
    const auto hydraulic = hydraulic_network();
    const auto result = StructuralMatcher{}.match(electrical, hydraulic);

    assert(result.mapping_class == MappingClass::StructuralIsomorphism);
    assert(result.node_mapping.size() == 4);
    assert(result.node_coverage == 1.0);
    assert(result.edge_coverage == 1.0);
    assert(result.invariant_coverage == 1.0);
    assert(result.preserved_invariants.size() == 1);
    assert(!result.caveats.empty()); // Structural matching is never promoted to proof.

    auto extended_target = hydraulic;
    extended_target.system_id = "hydraulic.extended";
    extended_target.nodes.push_back(
        {"reservoir", "Reservoir", NodeKind::Storage, Dimension{}});
    const auto embedding = StructuralMatcher{}.match(electrical, extended_target);
    assert(embedding.mapping_class == MappingClass::InducedSubgraphEmbedding);
    assert(embedding.node_coverage == 1.0);

    auto incompatible = hydraulic;
    incompatible.system_id = "hydraulic.incompatible";
    incompatible.edges[1].relation = "unrelated_relation";
    const auto rejected = StructuralMatcher{}.match(electrical, incompatible);
    assert(rejected.mapping_class == MappingClass::NoMatch);

    auto unchecked = hydraulic;
    unchecked.unit_status = UnitStatus::Unchecked;
    const auto not_physically_qualified =
        StructuralMatcher{}.match(electrical, unchecked);
    assert(not_physically_qualified.mapping_class == MappingClass::StructuralIsomorphism);
    bool warned_about_units = false;
    for (const auto& caveat : not_physically_qualified.caveats)
        warned_about_units = warned_about_units ||
            caveat.find("Dimensional validation is incomplete") != std::string::npos;
    assert(warned_about_units);

    const auto library = InvariantLibrary::core();
    assert(library.all().size() >= 8);

    bool duplicate_rejected = false;
    try {
        (void)InvariantLibrary({
            {"same", "First", "statement", {}, {}, {}, "reference"},
            {"same", "Second", "statement", {}, {}, {}, "reference"}
        });
    } catch (const std::invalid_argument&) {
        duplicate_rejected = true;
    }
    assert(duplicate_rejected);

    bool malformed_usr_rejected = false;
    auto malformed = electrical;
    malformed.edges.push_back({"missing", "bad", "battery"});
    try {
        expert_robot::cdam::validate_usr(malformed);
    } catch (const std::invalid_argument&) {
        malformed_usr_rejected = true;
    }
    assert(malformed_usr_rejected);
    return 0;
}
