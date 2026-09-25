#include "expert_robot/skills/math_skill.hpp"

#include <algorithm>
#include <stdexcept>
#include <unordered_set>
#include <utility>

namespace expert_robot::skills {

std::string_view skill_stage_name(SkillStage stage) {
    switch (stage) {
        case SkillStage::Experimental: return "experimental";
        case SkillStage::Qualified: return "qualified";
        case SkillStage::Deprecated: return "deprecated";
    }
    return "unknown";
}

MathSkillCatalog::MathSkillCatalog(
    std::vector<MathSkill> skills)
    : skills_(std::move(skills)) {
    std::unordered_set<std::string> ids;

    for (const auto& skill : skills_) {
        if (skill.skill_id.empty() ||
            skill.title.empty() ||
            skill.procedure.empty()) {
            throw std::invalid_argument(
                "math skill fields must be non-empty");
        }
        if (!ids.insert(skill.skill_id).second) {
            throw std::invalid_argument(
                "duplicate math skill id: " +
                skill.skill_id);
        }
    }
}

MathSkillCatalog MathSkillCatalog::builtins() {
    using L = imagination::ImaginationLens;
    using R = swarm::AgentRole;

    return MathSkillCatalog({
        {
            "math.analogy.transfer",
            "Structural analogy transfer",
            L::Analogy,
            R::Analogist,
            "Identify a structurally similar theorem in another domain; "
            "separate surface vocabulary from invariant structure; transfer "
            "only the mechanism; list the exact hypothesis correspondence.",
            true,
            SkillStage::Qualified
        },
        {
            "math.geometry.reframe",
            "Exact geometric reframing",
            L::Geometry,
            R::GeometrySpecialist,
            "Translate the target into exact geometric objects, incidence, "
            "orientation, metric, flow, or coordinate-free relations; state "
            "what algebraic facts must remain invariant under the translation.",
            true,
            SkillStage::Qualified
        },
        {
            "math.algebra.reframe",
            "Algebraic reframing",
            L::Algebra,
            R::Mathematician,
            "Search for factorization, operator identities, conserved "
            "quantities, modules, rings, fields, or canonical algebraic "
            "normal forms that expose the target.",
            true,
            SkillStage::Qualified
        },
        {
            "math.duality.search",
            "Duality search",
            L::Duality,
            R::Mathematician,
            "Construct a dual, adjoint, complement, primal-dual, or inverse "
            "problem; identify which quantity becomes simpler in the dual view.",
            true,
            SkillStage::Qualified
        },
        {
            "math.inversion.challenge",
            "Inversion and contradiction",
            L::Inversion,
            R::Skeptic,
            "Reverse the implication or assume the negation; propagate the "
            "consequences until a concrete obstruction, contradiction, or "
            "alternative structure appears.",
            true,
            SkillStage::Qualified
        },
        {
            "math.generalize.strengthen",
            "Strengthening/generalization",
            L::Generalization,
            R::Mathematician,
            "Search for a stronger theorem with cleaner invariants whose "
            "specialization yields the target; explicitly record the added "
            "generality and proof burden.",
            true,
            SkillStage::Qualified
        },
        {
            "math.simplify.toy_model",
            "Minimal toy-model reduction",
            L::Simplification,
            R::Mathematician,
            "Reduce to the smallest nontrivial instance, solve or characterize "
            "that instance, identify the indispensable mechanism, then state "
            "what is required to lift it.",
            true,
            SkillStage::Qualified
        },
        {
            "math.boundary.probe",
            "Boundary and extremal probing",
            L::BoundaryCase,
            R::Skeptic,
            "Probe equality, zero, singular, degenerate, extremal, low- and "
            "high-dimensional cases; use failures to discover missing "
            "hypotheses or sharper statements.",
            true,
            SkillStage::Qualified
        },
        {
            "math.spectral.reframe",
            "Spectral/operator reframing",
            L::Spectral,
            R::Mathematician,
            "Search for an operator, spectrum, eigenproblem, quadratic form, "
            "energy, resolvent, or variational principle that encodes the "
            "target."
        },
        {
            "math.topology.reframe",
            "Topological obstruction search",
            L::Topological,
            R::Mathematician,
            "Search for continuity, compactness, homotopy, homology, "
            "cohomology, winding, index, or obstruction structure that is "
            "stable under deformation.",
            true,
            SkillStage::Qualified
        },
        {
            "math.counterfactual.assumptions",
            "Counterfactual assumption analysis",
            L::Counterfactual,
            R::Skeptic,
            "Remove, weaken, reverse, or complexify one assumption at a time; "
            "record precisely what survives, what fails, and any resulting "
            "counterexample.",
            true,
            SkillStage::Qualified
        },
        {
            "math.construct.witness",
            "Explicit witness construction",
            L::Construction,
            R::Mathematician,
            "Build a canonical witness, normal form, recurrence, algorithm, "
            "or explicit object whose properties can be checked independently.",
            true,
            SkillStage::Qualified
        },
        {
            "math.lemma.high_leverage",
            "High-leverage lemma proposal",
            L::Lemma,
            R::LemmaProposer,
            "Identify one smaller statement that removes the dominant proof "
            "obstacle; keep the statement stronger than a tautology but cheaper "
            "than the parent; make it suitable for Lean formalization.",
            true,
            SkillStage::Qualified
        },
    });
}

const MathSkill& MathSkillCatalog::get(
    std::string_view skill_id) const {
    const auto it = std::find_if(
        skills_.begin(),
        skills_.end(),
        [&](const MathSkill& skill) {
            return skill.skill_id == skill_id;
        });
    if (it == skills_.end()) {
        throw std::out_of_range(
            "unknown math skill: " +
            std::string(skill_id));
    }
    return *it;
}

std::vector<MathSkill> MathSkillCatalog::for_lens(
    imagination::ImaginationLens lens) const {
    std::vector<MathSkill> result;
    for (const auto& skill : skills_) {
        if (skill.lens == lens) {
            result.push_back(skill);
        }
    }
    return result;
}

std::vector<MathSkill> MathSkillCatalog::qualified_for_lens(
    imagination::ImaginationLens lens) const {
    std::vector<MathSkill> result;
    for (const auto& skill : skills_) {
        if (skill.lens == lens &&
            skill.stage == SkillStage::Qualified) {
            result.push_back(skill);
        }
    }
    return result;
}

const std::vector<MathSkill>&
MathSkillCatalog::all() const noexcept {
    return skills_;
}

} // namespace expert_robot::skills
