#include "expert_robot/proof_search.hpp"
#include "expert_robot/research/route_planner.hpp"

#include <cassert>
#include <stdexcept>
#include <string_view>

namespace {

class HintRunner final : public expert_robot::ILeanRunner {
public:
    expert_robot::LeanRunResult run(
        std::string_view source) override {
        if (source.find(
                "exact MathAI.Helper") !=
            std::string_view::npos) {
            return {0, "accepted theorem reuse"};
        }
        return {1, "base tactic failed"};
    }
};

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    ProofRoute route{
        .kind =
            ProofRouteKind::ReuseVerifiedTheorem,
        .route_id = "route-1",
        .description = "reuse helper",
        .theorem_path = {
            "MathAI.Target",
            "MathAI.Helper"
        },
        .supporting_relations = {"USES"},
        .evidence_score = 0.9,
        .novelty_score = 0.2,
        .information_gain_score = 0.4,
        .expected_success_score = 0.8,
        .estimated_cost_score = 0.1,
        .diversity_score = 0.2,
        .final_score = 0.8,
        .requires_model = false,
        .requires_lean = true
    };

    const auto hints =
        lean_hint_tactics_for_route(route);
    assert(hints.size() == 3);
    assert(hints[0] == "exact MathAI.Helper");
    assert(hints[1] == "simpa using MathAI.Helper");
    assert(
        hints[2] ==
        "apply MathAI.Helper <;> aesop");

    const auto action =
        executable_action_for_route(route.kind);
    assert(!action.has_value());

    HintRunner runner;
    DeterministicProofSearch search(
        {"simp"},
        runner);

    SearchProblem problem;
    problem.statement = ": True";
    problem.candidate_name = "HintCandidate";
    problem.imports = {"MathAI"};
    problem.preferred_strategies = hints;

    const auto result =
        search.search(problem);

    assert(result.success);
    assert(result.attempts.size() == 1);
    assert(
        result.attempts[0].tactic ==
        "exact MathAI.Helper");
    assert(result.tactic.has_value());
    assert(
        *result.tactic ==
        "exact MathAI.Helper");

    // Without the route hint, the base tactic fails.
    SearchProblem unhinted = problem;
    unhinted.preferred_strategies.clear();
    const auto base =
        search.search(unhinted);
    assert(!base.success);
    assert(base.attempts.size() == 1);
    assert(base.attempts[0].tactic == "simp");

    bool unsafe_rejected = false;
    try {
        SearchProblem unsafe = problem;
        unsafe.preferred_strategies = {
            "exact by sorry"
        };
        (void)search.search(unsafe);
    } catch (const std::invalid_argument&) {
        unsafe_rejected = true;
    }
    assert(unsafe_rejected);

    ProofRoute advisory{
        .kind =
            ProofRouteKind::FollowTheoremPath,
        .route_id = "route-2",
        .description = "unverified path",
        .theorem_path = {
            "MathAI.Target",
            "MathAI.Unknown"
        }
    };
    assert(
        lean_hint_tactics_for_route(
            advisory).empty());

    return 0;
}
