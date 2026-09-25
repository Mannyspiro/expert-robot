#include "expert_robot/research/state_machine.hpp"

#include <cassert>
#include <stdexcept>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    ResearchStateMachine machine(
        ResearchBudget{
            .max_cycles = 16,
            .max_model_calls = 32,
            .max_proof_attempts = 64,
            .max_generated_ideas = 32,
            .max_generated_lemmas = 32
        });

    auto t = machine.step(ResearchObservation{});
    assert(t.to == ResearchPhase::RetrieveKnown);
    assert(t.action == ResearchAction::Retrieve);

    ResearchObservation retrieved;
    retrieved.retrieval_complete = true;
    t = machine.step(retrieved);
    assert(t.to == ResearchPhase::DirectProof);
    assert(t.action == ResearchAction::AttemptDirectProof);

    ResearchObservation direct_failed;
    direct_failed.direct_proof_failed = true;
    direct_failed.cognitive_action =
        cognition::CognitiveAction::ExploreNovelRoute;
    direct_failed.usage_delta.proof_attempts = 3;
    t = machine.step(direct_failed);
    assert(t.to == ResearchPhase::Imagine);
    assert(t.action == ResearchAction::RunImagination);

    ResearchObservation imagined;
    imagined.imagination_complete = true;
    imagined.shortlisted_candidates = 2;
    imagined.usage_delta.model_calls = 8;
    imagined.usage_delta.generated_ideas = 6;
    t = machine.step(imagined);
    assert(t.to == ResearchPhase::VerifyCandidate);
    assert(t.action == ResearchAction::VerifyCandidate);

    ResearchObservation helper_verified;
    helper_verified.verified_candidate_lemmas = 1;
    helper_verified.usage_delta.proof_attempts = 2;
    t = machine.step(helper_verified);
    assert(t.to == ResearchPhase::RetryParent);
    assert(t.action == ResearchAction::RetryParentProof);

    ResearchObservation retry_failed_after_helper;
    retry_failed_after_helper.parent_retry_failed = true;
    t = machine.step(retry_failed_after_helper);
    assert(t.to == ResearchPhase::Imagine);

    ResearchObservation imagined_again;
    imagined_again.imagination_complete = true;
    imagined_again.shortlisted_candidates = 1;
    t = machine.step(imagined_again);
    assert(t.to == ResearchPhase::VerifyCandidate);

    ResearchObservation candidate_failed;
    candidate_failed.candidate_verification_failed = true;
    candidate_failed.usage_delta.proof_attempts = 2;
    t = machine.step(candidate_failed);
    assert(t.to == ResearchPhase::Decompose);
    assert(t.action == ResearchAction::RunLemmaFactory);

    ResearchObservation decomposed;
    decomposed.decomposition_complete = true;
    decomposed.proven_child_lemmas = 2;
    decomposed.usage_delta.generated_lemmas = 3;
    decomposed.usage_delta.proof_attempts = 4;
    t = machine.step(decomposed);
    assert(t.to == ResearchPhase::RetryParent);
    assert(t.action == ResearchAction::RetryParentProof);

    ResearchObservation parent_verified;
    parent_verified.lean_verified = true;
    parent_verified.usage_delta.proof_attempts = 1;
    t = machine.step(parent_verified);
    assert(t.to == ResearchPhase::Consolidate);
    assert(t.action == ResearchAction::ConsolidateVerifiedKnowledge);
    assert(machine.state().any_lean_verified);

    t = machine.step(ResearchObservation{});
    assert(t.to == ResearchPhase::Complete);
    assert(t.action == ResearchAction::StopComplete);
    assert(machine.state().completed);

    bool terminal_rejected = false;
    try {
        (void)machine.step(ResearchObservation{});
    } catch (const std::logic_error&) {
        terminal_rejected = true;
    }
    assert(terminal_rejected);

    // A direct cognition choice can route immediately to recursive decomposition.
    machine.reset();
    (void)machine.step(ResearchObservation{});

    ResearchObservation retrieval_again;
    retrieval_again.retrieval_complete = true;
    (void)machine.step(retrieval_again);

    ResearchObservation decompose_choice;
    decompose_choice.direct_proof_failed = true;
    decompose_choice.cognitive_action =
        cognition::CognitiveAction::DecomposeProblem;
    t = machine.step(decompose_choice);
    assert(t.to == ResearchPhase::Decompose);

    // No surviving idea falls back to decomposition.
    machine.reset();
    (void)machine.step(ResearchObservation{});
    (void)machine.step(retrieval_again);
    (void)machine.step(direct_failed);

    ResearchObservation no_ideas;
    no_ideas.imagination_complete = true;
    no_ideas.shortlisted_candidates = 0;
    t = machine.step(no_ideas);
    assert(t.to == ResearchPhase::Decompose);

    // Hard resource pressure stops research without pretending success.
    machine.reset();
    ResearchObservation pressure;
    pressure.resource_pressure = 0.99;
    t = machine.step(pressure);
    assert(t.to == ResearchPhase::Exhausted);
    assert(t.action == ResearchAction::StopExhausted);
    assert(machine.state().exhausted);
    assert(!machine.state().completed);
    assert(!machine.state().any_lean_verified);

    // Budget exhaustion is deterministic.
    ResearchStateMachine tiny(
        ResearchBudget{
            .max_cycles = 2,
            .max_model_calls = 2,
            .max_proof_attempts = 2,
            .max_generated_ideas = 2,
            .max_generated_lemmas = 2
        });

    (void)tiny.step(ResearchObservation{});
    t = tiny.step(ResearchObservation{});
    assert(t.to == ResearchPhase::Exhausted);
    assert(t.action == ResearchAction::StopExhausted);

    // Conflicting success/failure observations are rejected.
    bool conflict_rejected = false;
    try {
        ResearchObservation conflict;
        conflict.lean_verified = true;
        conflict.direct_proof_failed = true;
        validate_research_observation(conflict);
    } catch (const std::invalid_argument&) {
        conflict_rejected = true;
    }
    assert(conflict_rejected);

    return 0;
}
