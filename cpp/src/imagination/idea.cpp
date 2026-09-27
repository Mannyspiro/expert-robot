#include "expert_robot/imagination/idea.hpp"

#include <algorithm>

namespace expert_robot::imagination {

double IdeaCandidate::final_score() const noexcept {
    const double risk =
        std::clamp(static_cast<double>(skeptic_risk) / 100.0, 0.0, 1.0);
    const double gate = skeptic_keep && skeptic_valid ? 1.0 : 0.0;
    return gate * std::clamp(
        quality_diversity_score * (1.0 - 0.45 * risk),
        0.0,
        1.0);
}

std::string_view lens_name(ImaginationLens lens) {
    switch (lens) {
        case ImaginationLens::Analogy: return "analogy";
        case ImaginationLens::Geometry: return "geometry";
        case ImaginationLens::Algebra: return "algebra";
        case ImaginationLens::Duality: return "duality";
        case ImaginationLens::Inversion: return "inversion";
        case ImaginationLens::Generalization: return "generalization";
        case ImaginationLens::Simplification: return "simplification";
        case ImaginationLens::BoundaryCase: return "boundary_case";
        case ImaginationLens::Spectral: return "spectral";
        case ImaginationLens::Topological: return "topological";
        case ImaginationLens::Counterfactual: return "counterfactual";
        case ImaginationLens::Construction: return "construction";
        case ImaginationLens::Lemma: return "lemma";
        case ImaginationLens::Count: break;
    }
    return "unknown";
}

swarm::AgentRole role_for_lens(ImaginationLens lens) {
    switch (lens) {
        case ImaginationLens::Analogy:
            return swarm::AgentRole::Analogist;
        case ImaginationLens::Geometry:
            return swarm::AgentRole::GeometrySpecialist;
        case ImaginationLens::Inversion:
        case ImaginationLens::BoundaryCase:
        case ImaginationLens::Counterfactual:
            return swarm::AgentRole::Skeptic;
        case ImaginationLens::Lemma:
            return swarm::AgentRole::LemmaProposer;
        case ImaginationLens::Algebra:
        case ImaginationLens::Duality:
        case ImaginationLens::Generalization:
        case ImaginationLens::Simplification:
        case ImaginationLens::Spectral:
        case ImaginationLens::Topological:
        case ImaginationLens::Construction:
        case ImaginationLens::Count:
            return swarm::AgentRole::Mathematician;
    }
    return swarm::AgentRole::Mathematician;
}

std::string lens_instruction(ImaginationLens lens) {
    switch (lens) {
        case ImaginationLens::Analogy:
            return "Find a structurally similar theorem or mechanism from another domain and transfer only the useful structure.";
        case ImaginationLens::Geometry:
            return "Re-express the problem geometrically: shapes, flows, incidence, metric, orientation, or exact geometric invariants.";
        case ImaginationLens::Algebra:
            return "Seek an algebraic reformulation using identities, operators, invariants, factorizations, or algebraic structure.";
        case ImaginationLens::Duality:
            return "Search for a dual, adjoint, complementary, primal-dual, or inverse viewpoint that changes the difficulty.";
        case ImaginationLens::Inversion:
            return "Reverse the direction of the argument, assume the opposite, or solve backward from the desired conclusion.";
        case ImaginationLens::Generalization:
            return "Look for a stronger or more general statement whose structure makes the target a simple corollary.";
        case ImaginationLens::Simplification:
            return "Strip the problem to the smallest nontrivial toy case, identify the mechanism, then lift it back.";
        case ImaginationLens::BoundaryCase:
            return "Probe equality, degenerate, extremal, low-dimensional, high-dimensional, zero, and limiting cases for hidden structure.";
        case ImaginationLens::Spectral:
            return "Seek an operator, eigenvalue, energy, quadratic-form, or spectral interpretation.";
        case ImaginationLens::Topological:
            return "Seek continuity, homotopy, homology/cohomology, winding, obstruction, compactness, or global-structure interpretations.";
        case ImaginationLens::Counterfactual:
            return "Change or remove one assumption and analyze what breaks, survives, or becomes a counterexample.";
        case ImaginationLens::Construction:
            return "Construct an explicit object, witness, canonical normal form, or algorithm that exposes the theorem mechanism.";
        case ImaginationLens::Lemma:
            return "Identify one high-leverage helper lemma whose proof would substantially reduce the target.";
        case ImaginationLens::Count:
            break;
    }
    return "Generate a mathematically distinct useful idea.";
}

} // namespace expert_robot::imagination
