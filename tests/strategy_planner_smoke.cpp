#include "expert_robot/research/route_memory.hpp"
#include "expert_robot/research/strategy_planner.hpp"

#include <cassert>
#include <filesystem>

namespace {

expert_robot::research::ProofRoute route(
    expert_robot::research::ProofRouteKind kind,
    const char* id,
    double score) {
    return expert_robot::research::ProofRoute{
        .kind = kind,
        .route_id = id,
        .description = id,
        .final_score = score
    };
}

expert_robot::research::ProofRouteSequence sequence(
    const char* id,
    std::vector<expert_robot::research::ProofRoute> steps,
    double score) {
    return expert_robot::research::ProofRouteSequence{
        .sequence_id = id,
        .steps = std::move(steps),
        .average_route_score = score,
        .synergy_score = 0.8,
        .final_score = score
    };
}

const expert_robot::research::ResearchStrategyPlan*
find_signature(
    const std::vector<expert_robot::research::ResearchStrategyPlan>& plans,
    const std::string& signature) {
    for (const auto& plan : plans) {
        if (plan.signature == signature) {
            return &plan;
        }
    }
    return nullptr;
}

} // namespace

int main() {
    using namespace expert_robot::research;

    const auto db =
        std::filesystem::temp_directory_path() /
        "expert-robot-strategy-planner.sqlite3";
    std::filesystem::remove(db);

    RouteOutcomeLedger memory(db);

    const auto seq_a =
        sequence(
            "seq-a",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-a",
                    0.72),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-a",
                    0.78),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-a",
                    0.74)
            },
            0.76);

    const auto seq_b =
        sequence(
            "seq-b",
            {
                route(
                    ProofRouteKind::ImaginationCandidate,
                    "imagine-b",
                    0.75),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-b",
                    0.74),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-b",
                    0.73)
            },
            0.75);

    ResearchStrategyPlanner baseline;

    const auto baseline_plans =
        baseline.plan(
            {seq_a, seq_b},
            "algebra");

    assert(baseline_plans.size() == 2);

    const std::string signature_a =
        research_strategy_signature(seq_a);
    const std::string signature_b =
        research_strategy_signature(seq_b);

    const auto* base_a =
        find_signature(
            baseline_plans,
            signature_a);
    const auto* base_b =
        find_signature(
            baseline_plans,
            signature_b);

    assert(base_a != nullptr);
    assert(base_b != nullptr);
    assert(
        base_a->strategy_id ==
        research_strategy_id(signature_a));
    assert(
        base_a->title ==
        "Reframe, decompose, verify");
    assert(
        base_b->title ==
        "Imagine, decompose, verify");

    for (int i = 0; i < 5; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    base_a->strategy_id,
                .signature =
                    base_a->signature,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });

        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    base_b->strategy_id,
                .signature =
                    base_b->signature,
                .domain = "algebra",
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });
    }

    const auto exp_a =
        memory.strategy_experience(
            base_a->strategy_id,
            "algebra");
    const auto exp_b =
        memory.strategy_experience(
            base_b->strategy_id,
            "algebra");

    assert(exp_a.attempts == 5);
    assert(exp_a.target_verifications == 5);
    assert(
        exp_a.smoothed_verified_rate() >
        exp_b.smoothed_verified_rate());
    assert(
        exp_a.average_resource_cost() <
        exp_b.average_resource_cost());

    ResearchStrategyPlanner learned(
        ResearchStrategyPlannerConfig{},
        &memory);

    // New theorem-specific route IDs, same research methods.
    const auto seq_a_new =
        sequence(
            "seq-a-new-theorem",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-new",
                    0.70),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-new",
                    0.76),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-new",
                    0.72)
            },
            0.74);

    const auto seq_b_new =
        sequence(
            "seq-b-new-theorem",
            {
                route(
                    ProofRouteKind::ImaginationCandidate,
                    "imagine-new",
                    0.76),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-new-b",
                    0.75),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-new-b",
                    0.74)
            },
            0.75);

    const auto learned_plans =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");

    const auto* learned_a =
        find_signature(
            learned_plans,
            signature_a);
    const auto* learned_b =
        find_signature(
            learned_plans,
            signature_b);

    assert(learned_a != nullptr);
    assert(learned_b != nullptr);

    // Cross-theorem strategy evidence overcomes the small raw sequence-score
    // advantage of the historically weak method.
    assert(
        learned_a->final_score >
        learned_b->final_score);
    assert(
        learned_a->experience_adjustment >
        0.0);
    assert(
        learned_b->experience_adjustment <
        0.0);
    assert(
        learned_a->evidence_confidence > 0.0);
    assert(
        learned_a->evidence_confidence < 1.0);
    assert(learned_a->step_evidence_steps == 0U);
    assert(learned_a->step_evidence_confidence == 0.0);
    assert(learned_a->step_adjustment == 0.0);

    const double early_confidence =
        learned_a->evidence_confidence;
    const double early_adjustment =
        learned_a->experience_adjustment;

    for (int i = 0; i < 15; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    learned_a->strategy_id,
                .signature =
                    learned_a->signature,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });
    }

    const auto mature =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* mature_a =
        find_signature(
            mature,
            signature_a);

    assert(mature_a != nullptr);
    assert(
        mature_a->evidence_confidence >
        early_confidence);
    assert(
        mature_a->experience_adjustment >
        early_adjustment);

    // Persistent poor/high-cost performance causes reversible soft retirement.
    for (int i = 0; i < 5; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    learned_b->strategy_id,
                .signature =
                    learned_b->signature,
                .domain = "algebra",
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });
    }

    const auto retired =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* retired_b =
        find_signature(
            retired,
            signature_b);

    assert(retired_b != nullptr);
    assert(retired_b->soft_retired);
    assert(
        retired_b->soft_retirement_penalty >
        0.0);

    // Soft retirement never deletes the method and clears automatically when
    // substantial later verified evidence reverses the historical result.
    for (int i = 0; i < 30; ++i) {
        memory.record_strategy(
            ResearchStrategyOutcome{
                .strategy_id =
                    learned_b->strategy_id,
                .signature =
                    learned_b->signature,
                .domain = "algebra",
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });
    }

    const auto recovered =
        learned.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* recovered_b =
        find_signature(
            recovered,
            signature_b);

    assert(recovered_b != nullptr);
    assert(!recovered_b->soft_retired);
    assert(
        recovered_b->soft_retirement_penalty ==
        0.0);

    // Strategy evidence must remain domain-specific.
    const auto geometry =
        learned.plan(
            {seq_a_new, seq_b_new},
            "geometry");

    const auto* geometry_a =
        find_signature(
            geometry,
            signature_a);
    assert(geometry_a != nullptr);
    assert(
        geometry_a->experience_adjustment ==
        0.0);
    assert(
        geometry_a->evidence_confidence ==
        0.0);

    // Step evidence remains inert while sparse, then contributes only a
    // small bounded domain-specific adjustment after repeated observations.
    const auto step_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-step-strategy.sqlite3";
    std::filesystem::remove(step_db);

    RouteOutcomeLedger step_memory(step_db);
    ResearchStrategyPlanner step_planner(
        ResearchStrategyPlannerConfig{},
        &step_memory);

    const auto record_step_pair =
        [&]() {
            step_memory.record_strategy_step(
                ResearchStrategyStepOutcome{
                    .strategy_id =
                        research_strategy_id(signature_a),
                    .signature = signature_a,
                    .domain = "algebra",
                    .context_key = "",
                    .step_index = 0U,
                    .kind =
                        ProofRouteKind::RepresentationSwitch,
                    .route_id = "step-switch-good",
                    .verified_progress = true,
                    .target_verified = true,
                    .dead_end_escaped = true,
                    .resource_cost = 0.20,
                    .proof_attempts = 1,
                    .model_calls = 0,
                    .generated_ideas = 0,
                    .generated_lemmas = 0
                });

            step_memory.record_strategy_step(
                ResearchStrategyStepOutcome{
                    .strategy_id =
                        research_strategy_id(signature_b),
                    .signature = signature_b,
                    .domain = "algebra",
                    .context_key = "",
                    .step_index = 0U,
                    .kind =
                        ProofRouteKind::ImaginationCandidate,
                    .route_id = "step-imagine-poor",
                    .verified_progress = false,
                    .target_verified = false,
                    .dead_end_escaped = false,
                    .resource_cost = 0.80,
                    .proof_attempts = 1,
                    .model_calls = 1,
                    .generated_ideas = 1,
                    .generated_lemmas = 0
                });
        };

    for (int i = 0; i < 5; ++i) {
        record_step_pair();
    }

    const auto sparse_steps =
        step_planner.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* sparse_step_a =
        find_signature(
            sparse_steps,
            signature_a);
    const auto* sparse_step_b =
        find_signature(
            sparse_steps,
            signature_b);

    assert(sparse_step_a != nullptr);
    assert(sparse_step_b != nullptr);
    assert(sparse_step_a->step_adjustment == 0.0);
    assert(sparse_step_b->step_adjustment == 0.0);
    assert(sparse_step_a->step_evidence_steps == 0U);
    assert(sparse_step_b->step_evidence_steps == 0U);

    for (int i = 0; i < 3; ++i) {
        record_step_pair();
    }

    const auto mature_steps =
        step_planner.plan(
            {seq_a_new, seq_b_new},
            "algebra");
    const auto* mature_step_a =
        find_signature(
            mature_steps,
            signature_a);
    const auto* mature_step_b =
        find_signature(
            mature_steps,
            signature_b);

    assert(mature_step_a != nullptr);
    assert(mature_step_b != nullptr);
    assert(mature_step_a->step_evidence_steps == 1U);
    assert(mature_step_b->step_evidence_steps == 1U);
    assert(mature_step_a->step_evidence_confidence > 0.0);
    assert(mature_step_a->step_evidence_confidence < 1.0);
    assert(mature_step_a->step_adjustment > 0.0);
    assert(mature_step_b->step_adjustment < 0.0);
    assert(mature_step_a->step_adjustment <= 0.04);
    assert(mature_step_b->step_adjustment >= -0.04);
    assert(mature_step_a->final_score > mature_step_b->final_score);

    const auto step_geometry =
        step_planner.plan(
            {seq_a_new, seq_b_new},
            "geometry");
    const auto* step_geometry_a =
        find_signature(
            step_geometry,
            signature_a);
    assert(step_geometry_a != nullptr);
    assert(step_geometry_a->step_adjustment == 0.0);
    assert(step_geometry_a->step_evidence_steps == 0U);

    std::filesystem::remove(step_db);

    // Context-specific evidence can reverse ordering within the same domain
    // without changing the broad domain prior.
    const auto context_db =
        std::filesystem::temp_directory_path() /
        "expert-robot-context-strategy.sqlite3";
    std::filesystem::remove(context_db);

    RouteOutcomeLedger context_memory(
        context_db);

    const ResearchStrategyContext reframe_context{
        .domain = "algebra",
        .theorem_graph_coverage = 0.90,
        .uncertainty = 0.20,
        .route_repetition = 0.20,
        .consecutive_failures = 2,
        .decomposition_value = 0.45,
        .counterexample_value = 0.10,
        .abstraction_value = 0.25,
        .compression_value = 0.30,
        .representation_switch_value = 0.95
    };

    const ResearchStrategyContext imagine_context{
        .domain = "algebra",
        .theorem_graph_coverage = 0.10,
        .uncertainty = 0.90,
        .route_repetition = 0.90,
        .consecutive_failures = 8,
        .decomposition_value = 0.55,
        .counterexample_value = 0.20,
        .abstraction_value = 0.85,
        .compression_value = 0.30,
        .representation_switch_value = 0.25
    };

    const std::string reframe_key =
        research_strategy_context_key(
            reframe_context);
    const std::string imagine_key =
        research_strategy_context_key(
            imagine_context);

    assert(reframe_key != imagine_key);
    assert(
        reframe_key.find("graph=high") !=
        std::string::npos);
    assert(
        reframe_key.find("need=reframe") !=
        std::string::npos);
    assert(
        imagine_key.find("uncertainty=high") !=
        std::string::npos);
    assert(
        imagine_key.find("failures=stuck") !=
        std::string::npos);

    for (int i = 0; i < 6; ++i) {
        context_memory.record_strategy_context(
            ResearchStrategyContextOutcome{
                .strategy_id =
                    research_strategy_id(signature_a),
                .signature = signature_a,
                .context_key = reframe_key,
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });
        context_memory.record_strategy_context(
            ResearchStrategyContextOutcome{
                .strategy_id =
                    research_strategy_id(signature_b),
                .signature = signature_b,
                .context_key = reframe_key,
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });

        context_memory.record_strategy_context(
            ResearchStrategyContextOutcome{
                .strategy_id =
                    research_strategy_id(signature_a),
                .signature = signature_a,
                .context_key = imagine_key,
                .verified_progress = false,
                .target_verified = false,
                .dead_end_escaped = false,
                .resource_cost = 0.80
            });
        context_memory.record_strategy_context(
            ResearchStrategyContextOutcome{
                .strategy_id =
                    research_strategy_id(signature_b),
                .signature = signature_b,
                .context_key = imagine_key,
                .verified_progress = true,
                .target_verified = true,
                .dead_end_escaped = true,
                .resource_cost = 0.20
            });
    }

    ResearchStrategyPlanner contextual_planner(
        ResearchStrategyPlannerConfig{},
        &context_memory);

    const auto reframe_plans =
        contextual_planner.plan(
            {seq_a_new, seq_b_new},
            "algebra",
            &reframe_context);
    const auto imagine_plans =
        contextual_planner.plan(
            {seq_a_new, seq_b_new},
            "algebra",
            &imagine_context);
    const auto no_context_plans =
        contextual_planner.plan(
            {seq_a_new, seq_b_new},
            "algebra");

    const auto* reframe_a =
        find_signature(
            reframe_plans,
            signature_a);
    const auto* reframe_b =
        find_signature(
            reframe_plans,
            signature_b);
    const auto* imagine_a =
        find_signature(
            imagine_plans,
            signature_a);
    const auto* imagine_b =
        find_signature(
            imagine_plans,
            signature_b);
    const auto* no_context_a =
        find_signature(
            no_context_plans,
            signature_a);
    const auto* no_context_b =
        find_signature(
            no_context_plans,
            signature_b);

    assert(reframe_a != nullptr);
    assert(reframe_b != nullptr);
    assert(imagine_a != nullptr);
    assert(imagine_b != nullptr);
    assert(no_context_a != nullptr);
    assert(no_context_b != nullptr);

    assert(reframe_a->context_adjustment > 0.0);
    assert(reframe_b->context_adjustment < 0.0);
    assert(reframe_a->final_score > reframe_b->final_score);

    assert(imagine_a->context_adjustment < 0.0);
    assert(imagine_b->context_adjustment > 0.0);
    assert(imagine_b->final_score > imagine_a->final_score);

    assert(no_context_a->context_adjustment == 0.0);
    assert(no_context_b->context_adjustment == 0.0);
    assert(no_context_b->base_score > no_context_a->base_score);

    std::filesystem::remove(context_db);

    // Two theorem-specific sequences with the same move signature collapse to
    // one strategy and retain the stronger exemplar.
    const auto seq_a_weaker =
        sequence(
            "seq-a-weaker",
            {
                route(
                    ProofRouteKind::RepresentationSwitch,
                    "switch-weak",
                    0.60),
                route(
                    ProofRouteKind::RecursiveDecomposition,
                    "decompose-weak",
                    0.61),
                route(
                    ProofRouteKind::IntensifyVerification,
                    "verify-weak",
                    0.62)
            },
            0.61);

    const auto collapsed =
        learned.plan(
            {seq_a_new, seq_a_weaker},
            "algebra");

    assert(collapsed.size() == 1);
    assert(
        collapsed.front().
            exemplar_sequence.sequence_id ==
        "seq-a-new-theorem");

    std::filesystem::remove(db);
    return 0;
}
