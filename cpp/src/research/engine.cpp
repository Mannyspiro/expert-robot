#include "expert_robot/research/engine.hpp"

#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>

namespace expert_robot::research {
namespace {

void append_unique(
    std::vector<std::string>& values,
    const std::string& value) {
    if (value.empty()) return;

    if (std::find(
            values.begin(),
            values.end(),
            value) == values.end()) {
        values.push_back(value);
    }
}

std::size_t proof_attempts(
    const FormalizationResult& result) {
    return result.search.attempts.size();
}

std::size_t lemma_tree_attempts(
    const LemmaFactoryNode& node) {
    std::size_t total = 0;

    if (node.initial_result) {
        total +=
            node.initial_result->
                search.attempts.size();
    }

    if (node.retry_result) {
        total +=
            node.retry_result->
                search.attempts.size();
    }

    for (const auto& child :
         node.children) {
        total +=
            lemma_tree_attempts(child);
    }

    return total;
}

void collect_proven_child_candidates(
    const LemmaFactoryNode& node,
    bool include_node,
    std::vector<CandidateVerification>& output) {
    if (include_node) {
        const auto* proven =
            node.proven_result();

        if (proven != nullptr &&
            proven->lean_declaration) {
            output.push_back(
                CandidateVerification{
                    .idea_id =
                        "lemma_factory:" +
                        node.proposal.qualified_name(),
                    .proposal_generated = true,
                    .proposal =
                        node.proposal,
                    .formalization =
                        *proven,
                    .error = "",
                });
        }
    }

    for (const auto& child :
         node.children) {
        collect_proven_child_candidates(
            child,
            true,
            output);
    }
}

double conservative_resource_pressure(
    const cognition::InteroceptiveSensors& sensors) {
    return std::clamp(
        std::max({
            sensors.cpu_load,
            sensors.gpu_load,
            sensors.ram_pressure,
            sensors.vram_pressure,
            sensors.context_utilization,
            sensors.work_queue_pressure
        }),
        0.0,
        1.0);
}

void update_failure_sensors(
    cognition::InteroceptiveSensors& sensors,
    std::size_t attempts,
    const cognition::LogicalAssessment& logic) {
    sensors.recent_proof_success_rate = 0.0;
    sensors.verified_progress = 0.0;
    sensors.expected_verified_progress =
        std::clamp(
            logic.expected_success,
            0.0,
            1.0);

    sensors.consecutive_failures +=
        attempts;
    sensors.attempts_since_verified_progress +=
        attempts;

    sensors.route_repetition =
        std::clamp(
            sensors.route_repetition + 0.10,
            0.0,
            1.0);

    sensors.uncertainty =
        std::clamp(
            std::max(
                sensors.uncertainty,
                0.50),
            0.0,
            1.0);
}

void update_helper_success_sensors(
    cognition::InteroceptiveSensors& sensors,
    std::size_t verified_helpers) {
    if (verified_helpers == 0U) return;

    sensors.recent_proof_success_rate =
        std::clamp(
            0.25 +
                0.15 *
                    static_cast<double>(
                        verified_helpers),
            0.0,
            1.0);

    sensors.verified_progress =
        std::clamp(
            0.20 +
                0.10 *
                    static_cast<double>(
                        verified_helpers),
            0.0,
            0.80);

    sensors.consecutive_failures = 0U;
    sensors.attempts_since_verified_progress = 0U;
    sensors.route_repetition =
        std::max(
            0.0,
            sensors.route_repetition - 0.20);
}

ResearchUsage imagination_usage(
    const imagination::ImaginationRun& run) {
    // Conservative model-call accounting: one divergent call per selected
    // lens, up to one skeptic call per generated idea, plus synthesis.
    const std::size_t calls =
        run.selected_lenses.size() +
        run.generated.size() +
        (run.synthesis_ok ? 1U : 0U);

    return ResearchUsage{
        .cycles = 0,
        .model_calls = calls,
        .proof_attempts = 0,
        .generated_ideas =
            run.generated.size(),
        .generated_lemmas = 0,
    };
}

void append_transition(
    ResearchEpisodeLedger& ledger,
    const std::string& episode_id,
    const ResearchTransition& transition,
    const ResearchState& state) {
    (void)ledger.append_transition(
        episode_id,
        transition,
        state);
}

CandidateVerification target_candidate(
    const FormalizationProposal& target,
    const FormalizationResult& formalization) {
    return CandidateVerification{
        .idea_id =
            "target:" +
            target.qualified_name(),
        .proposal_generated = true,
        .proposal = target,
        .formalization = formalization,
        .error = "",
    };
}

bool research_action_seen(
    const ResearchState& state,
    ResearchAction action) {
    return std::any_of(
        state.history.begin(),
        state.history.end(),
        [&](const ResearchTransition& transition) {
            return transition.action == action;
        });
}

bool strategy_step_executed(
    const ProofRoute& step,
    const std::unordered_set<std::string>& attempted_route_ids,
    const ResearchState& state) {
    if (attempted_route_ids.contains(
            step.route_id)) {
        return true;
    }

    switch (step.kind) {
        case ProofRouteKind::RecursiveDecomposition:
            return research_action_seen(
                state,
                ResearchAction::RunLemmaFactory);

        case ProofRouteKind::ImaginationCandidate:
            return research_action_seen(
                state,
                ResearchAction::RunImagination);

        case ProofRouteKind::IntensifyVerification:
            // A parent retry after new verified information is the natural
            // state-machine realization of "verify harder".
            return research_action_seen(
                state,
                ResearchAction::RetryParentProof);

        case ProofRouteKind::RepresentationSwitch:
        case ProofRouteKind::CounterexampleSearch:
        case ProofRouteKind::ReuseVerifiedTheorem:
        case ProofRouteKind::FollowTheoremPath:
            return false;
    }

    return false;
}

} // namespace

MathResearchEngine::MathResearchEngine(
    IProofSearcher& searcher,
    cognition::CognitionController& cognition,
    imagination::ImaginationController& imagination,
    RecursiveLemmaFactory& lemma_factory,
    CandidateVerifier& candidate_verifier,
    VerifiedKnowledgeConsolidator& consolidator,
    ResearchEpisodeLedger& episode_ledger,
    MathResearchEngineConfig config,
    ProofRoutePlanner* route_planner,
    RouteOutcomeLedger* route_memory,
    skills::SkillLedger* skill_ledger,
    ResearchStrategyPlanner* strategy_planner)
    : searcher_(searcher),
      cognition_(cognition),
      imagination_(imagination),
      lemma_factory_(lemma_factory),
      candidate_verifier_(candidate_verifier),
      consolidator_(consolidator),
      episode_ledger_(episode_ledger),
      config_(config),
      route_planner_(route_planner),
      route_memory_(route_memory),
      skill_ledger_(skill_ledger),
      strategy_planner_(strategy_planner) {
    validate_research_budget(
        config_.budget);

    if (config_.max_dispatch_steps == 0U) {
        throw std::invalid_argument(
            "math research max_dispatch_steps must be positive");
    }
}

ResearchOutcome MathResearchEngine::run(
    ResearchProblem problem) {
    if (problem.episode_id.empty()) {
        throw std::invalid_argument(
            "research problem episode_id must be non-empty");
    }

    validate_formalization_proposal(
        problem.target);
    cognition::validate_logical_assessment(
        problem.logic);
    cognition::validate_interoceptive_sensors(
        problem.sensors);

    cognition_.reset_transient_state();

    ResearchStateMachine machine(
        config_.budget);

    ResearchOutcome outcome;
    std::vector<std::string> helper_context;
    std::vector<CandidateVerification>
        verified_helpers;

    const std::string target_name =
        problem.target.qualified_name();

    {
        std::ostringstream payload;
        payload
            << "target=" << target_name << "\n"
            << "statement_sha256="
            << sha256_hex(
                problem.target.statement())
            << "\n"
            << "domain="
            << problem.target.domain
            << "\n";

        (void)episode_ledger_.append(
            problem.episode_id,
            "episode_started",
            payload.str());
    }

    auto transition =
        machine.step(
            ResearchObservation{});
    append_transition(
        episode_ledger_,
        problem.episode_id,
        transition,
        machine.state());

    std::optional<cognition::CognitionCycle>
        latest_cognition;
    std::vector<std::string>
        pending_preferred_strategies;
    std::unordered_set<std::string>
        attempted_route_ids;

    auto refresh_route_plan = [&](
        const imagination::ImaginationRun* imagined,
        bool select_for_dispatch)
        -> std::optional<cognition::CognitiveAction> {
        if (route_planner_ == nullptr ||
            !latest_cognition) {
            return std::nullopt;
        }

        outcome.planned_routes =
            route_planner_->plan(
                RoutePlanningRequest{
                    .target_name =
                        problem.focus_theorem.empty()
                            ? target_name
                            : problem.focus_theorem,
                    .target_domain =
                        problem.target.domain,
                    .cognitive_action =
                        latest_cognition->decision.action,
                    .logic = problem.logic,
                    .imagination = imagined,
                });

        outcome.planned_sequences =
            route_planner_->compose(
                outcome.planned_routes,
                problem.target.domain);

        outcome.planned_strategies.clear();
        if (strategy_planner_ != nullptr) {
            outcome.planned_strategies =
                strategy_planner_->plan(
                    outcome.planned_sequences,
                    problem.target.domain);

            if (!outcome.planned_strategies.empty()) {
                const auto& strategy =
                    outcome.planned_strategies.front();

                std::ostringstream payload;
                payload
                    << "strategy_id="
                    << strategy.strategy_id
                    << "\nsignature="
                    << strategy.signature
                    << "\ntitle="
                    << strategy.title
                    << "\nscore="
                    << strategy.final_score
                    << "\nbase_score="
                    << strategy.base_score
                    << "\nexperience_adjustment="
                    << strategy.experience_adjustment
                    << "\nexploration_bonus="
                    << strategy.exploration_bonus
                    << "\nsequence_id="
                    << strategy.exemplar_sequence.sequence_id;

                (void)episode_ledger_.append(
                    problem.episode_id,
                    "research_strategy_top",
                    payload.str());
            }
        }

        if (!outcome.planned_sequences.empty()) {
            const auto& sequence =
                outcome.planned_sequences.front();

            std::ostringstream payload;
            payload
                << "sequence_id="
                << sequence.sequence_id
                << "\nscore="
                << sequence.final_score
                << "\nsynergy="
                << sequence.synergy_score
                << "\nsteps="
                << sequence.steps.size();

            for (std::size_t i = 0U;
                 i < sequence.steps.size();
                 ++i) {
                payload
                    << "\nstep_"
                    << i
                    << "="
                    << proof_route_kind_name(
                        sequence.steps[i].kind)
                    << ":"
                    << sequence.steps[i].route_id;
            }

            (void)episode_ledger_.append(
                problem.episode_id,
                "route_sequence_top",
                payload.str());
        }

        if (!outcome.planned_routes.empty()) {
            const auto& top =
                outcome.planned_routes.front();

            std::ostringstream payload;
            payload
                << "route_id=" << top.route_id
                << "\nkind="
                << proof_route_kind_name(top.kind)
                << "\nscore=" << top.final_score
                << "\ndescription="
                << top.description;

            (void)episode_ledger_.append(
                problem.episode_id,
                "route_plan_top",
                payload.str());
        }

        if (!select_for_dispatch) {
            return std::nullopt;
        }

        struct DispatchCandidate {
            const ProofRoute* route{nullptr};
            const ProofRouteSequence* sequence{nullptr};
            const ResearchStrategyPlan* strategy{nullptr};
        };

        std::vector<DispatchCandidate>
            dispatch_candidates;
        std::unordered_set<std::string>
            queued_route_ids;

        if (!outcome.planned_strategies.empty()) {
            const auto& strategy =
                outcome.planned_strategies.front();
            const auto& sequence =
                strategy.exemplar_sequence;

            for (const auto& route :
                 sequence.steps) {
                if (queued_route_ids.insert(
                        route.route_id).second) {
                    dispatch_candidates.push_back(
                        DispatchCandidate{
                            .route = &route,
                            .sequence = &sequence,
                            .strategy = &strategy,
                        });
                }
            }
        } else if (!outcome.planned_sequences.empty()) {
            const auto& sequence =
                outcome.planned_sequences.front();

            for (const auto& route :
                 sequence.steps) {
                if (queued_route_ids.insert(
                        route.route_id).second) {
                    dispatch_candidates.push_back(
                        DispatchCandidate{
                            .route = &route,
                            .sequence = &sequence,
                            .strategy = nullptr,
                        });
                }
            }
        }

        for (const auto& route :
             outcome.planned_routes) {
            if (queued_route_ids.insert(
                    route.route_id).second) {
                dispatch_candidates.push_back(
                    DispatchCandidate{
                        .route = &route,
                        .sequence = nullptr,
                        .strategy = nullptr,
                    });
            }
        }

        for (const auto& candidate :
             dispatch_candidates) {
            if (candidate.route == nullptr) {
                continue;
            }

            const auto& route =
                *candidate.route;

            if (attempted_route_ids.contains(
                    route.route_id)) {
                continue;
            }

            const auto hints =
                lean_hint_tactics_for_route(
                    route);

            const auto remember_dispatch =
                [&]() {
                    attempted_route_ids.insert(
                        route.route_id);
                    outcome.dispatched_route =
                        route;

                    if (candidate.sequence != nullptr) {
                        outcome.dispatched_sequence =
                            *candidate.sequence;
                    } else {
                        outcome.dispatched_sequence.reset();
                    }

                    if (candidate.strategy != nullptr) {
                        outcome.dispatched_strategy =
                            *candidate.strategy;
                    } else {
                        outcome.dispatched_strategy.reset();
                    }
                };

            if (!hints.empty()) {
                remember_dispatch();
                pending_preferred_strategies =
                    hints;

                std::ostringstream payload;
                payload
                    << "route_id="
                    << route.route_id
                    << "\nkind="
                    << proof_route_kind_name(
                        route.kind)
                    << "\naction="
                    << cognition::
                        cognitive_action_name(
                            cognition::
                                CognitiveAction::
                                    ContinueCurrentRoute)
                    << "\nhints="
                    << hints.size()
                    << "\nscore="
                    << route.final_score;

                if (outcome.dispatched_sequence) {
                    payload
                        << "\nsequence_id="
                        << outcome.dispatched_sequence->
                            sequence_id;
                }

                if (outcome.dispatched_strategy) {
                    payload
                        << "\nstrategy_id="
                        << outcome.dispatched_strategy->
                            strategy_id
                        << "\nstrategy_signature="
                        << outcome.dispatched_strategy->
                            signature;

                    (void)episode_ledger_.append(
                        problem.episode_id,
                        "research_strategy_dispatched",
                        payload.str());
                }

                (void)episode_ledger_.append(
                    problem.episode_id,
                    "route_dispatched",
                    payload.str());

                return cognition::
                    CognitiveAction::
                        ContinueCurrentRoute;
            }

            const auto action =
                executable_action_for_route(
                    route.kind);
            if (!action.has_value()) {
                continue;
            }

            remember_dispatch();

            std::ostringstream payload;
            payload
                << "route_id=" << route.route_id
                << "\nkind="
                << proof_route_kind_name(route.kind)
                << "\naction="
                << cognition::cognitive_action_name(
                    *action)
                << "\nscore="
                << route.final_score;

            if (outcome.dispatched_sequence) {
                payload
                    << "\nsequence_id="
                    << outcome.dispatched_sequence->
                        sequence_id;
            }

            if (outcome.dispatched_strategy) {
                payload
                    << "\nstrategy_id="
                    << outcome.dispatched_strategy->
                        strategy_id
                    << "\nstrategy_signature="
                    << outcome.dispatched_strategy->
                        signature;

                (void)episode_ledger_.append(
                    problem.episode_id,
                    "research_strategy_dispatched",
                    payload.str());
            }

            (void)episode_ledger_.append(
                problem.episode_id,
                "route_dispatched",
                payload.str());

            return action;
        }

        return std::nullopt;
    };

    for (std::size_t dispatch = 0;
         dispatch < config_.max_dispatch_steps;
         ++dispatch) {
        const auto phase =
            machine.state().phase;

        if (phase ==
                ResearchPhase::Complete ||
            phase ==
                ResearchPhase::Exhausted) {
            break;
        }

        switch (phase) {
            case ResearchPhase::Intake:
                throw std::logic_error(
                    "research engine returned unexpectedly to intake");

            case ResearchPhase::RetrieveKnown: {
                // The cheapest first attempt should use already-verified
                // theorem-graph knowledge before broad exploration. Only
                // relation-aware routes that produce safe Lean hints can enter
                // the preferred strategy list.
                if (route_planner_ != nullptr) {
                    const auto known_routes =
                        route_planner_->plan(
                            RoutePlanningRequest{
                                .target_name =
                                    problem.focus_theorem.empty()
                                        ? target_name
                                        : problem.focus_theorem,
                                .target_domain =
                                    problem.target.domain,
                                .cognitive_action =
                                    cognition::CognitiveAction::
                                        ContinueCurrentRoute,
                                .logic = problem.logic,
                                .imagination = nullptr,
                            });

                    if (outcome.planned_routes.empty()) {
                        outcome.planned_routes =
                            known_routes;
                    }

                    for (const auto& route :
                         known_routes) {
                        const auto hints =
                            lean_hint_tactics_for_route(
                                route);
                        if (hints.empty()) {
                            continue;
                        }

                        pending_preferred_strategies =
                            hints;
                        attempted_route_ids.insert(
                            route.route_id);
                        outcome.dispatched_route =
                            route;

                        std::ostringstream payload;
                        payload
                            << "route_id="
                            << route.route_id
                            << "\nkind="
                            << proof_route_kind_name(
                                route.kind)
                            << "\nhints="
                            << hints.size()
                            << "\nscore="
                            << route.final_score;

                        (void)episode_ledger_.append(
                            problem.episode_id,
                            "retrieval_route_hint",
                            payload.str());
                        break;
                    }
                }

                ResearchObservation observation;
                observation.retrieval_complete = true;
                observation.resource_pressure =
                    conservative_resource_pressure(
                        problem.sensors);

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::DirectProof: {
                auto direct =
                    formalize(
                        problem.target,
                        searcher_,
                        helper_context,
                        pending_preferred_strategies);

                pending_preferred_strategies.clear();

                ResearchObservation observation;
                observation.usage_delta.proof_attempts =
                    proof_attempts(direct);

                if (direct.proven()) {
                    outcome.target_result =
                        direct;
                    observation.lean_verified =
                        true;
                } else {
                    update_failure_sensors(
                        problem.sensors,
                        direct.search.attempts.size(),
                        problem.logic);

                    latest_cognition =
                        cognition_.step(
                            problem.sensors,
                            problem.logic);

                    observation.direct_proof_failed =
                        true;
                    observation.resource_pressure =
                        latest_cognition->
                            interoception.state.
                            resource_pressure;

                    const auto route_action =
                        refresh_route_plan(
                            nullptr,
                            true);

                    observation.cognitive_action =
                        route_action.value_or(
                            latest_cognition->
                                decision.action);

                    std::ostringstream payload;
                    payload
                        << "action="
                        << cognition::
                            cognitive_action_name(
                                observation.
                                    cognitive_action)
                        << "\n"
                        << "breakthrough="
                        << (latest_cognition->
                                    decision.
                                    breakthrough_mode
                                ? "true"
                                : "false")
                        << "\n";

                    (void)episode_ledger_.append(
                        problem.episode_id,
                        "cognition_decision",
                        payload.str());
                }

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::Imagine: {
                latest_cognition =
                    cognition_.step(
                        problem.sensors,
                        problem.logic);

                auto imagined =
                    imagination_.run(
                        imagination::ImaginationRequest{
                            .request_id =
                                problem.episode_id +
                                ":imagination:" +
                                std::to_string(
                                    machine.state().
                                        usage.cycles),
                            .goal =
                                problem.target.
                                    statement(),
                            .context =
                                problem.context,
                            .focus_theorem =
                                problem.focus_theorem,
                            .personality =
                                cognition_.
                                    personality(),
                            .cognition =
                                *latest_cognition,
                            .logic =
                                problem.logic,
                            .evaluation_mode =
                                problem.
                                    evaluation_mode,
                            .experimental_skills =
                                problem.
                                    experimental_skills,
                        });

                outcome.last_imagination =
                    imagined;

                (void)refresh_route_plan(
                    &*outcome.last_imagination,
                    false);

                ResearchObservation observation;
                observation.imagination_complete =
                    true;
                observation.shortlisted_candidates =
                    imagined.shortlisted.size();
                observation.resource_pressure =
                    latest_cognition->
                        interoception.state.
                        resource_pressure;
                observation.usage_delta =
                    imagination_usage(
                        imagined);

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::VerifyCandidate: {
                if (!outcome.last_imagination) {
                    throw std::logic_error(
                        "candidate verification requested without imagination output");
                }

                const auto verifications =
                    candidate_verifier_.verify(
                        problem.target.statement(),
                        problem.target.domain,
                        outcome.last_imagination->
                            shortlisted,
                        problem.context);

                std::size_t verified_count = 0;
                std::size_t attempts = 0;

                for (const auto& candidate :
                     verifications) {
                    outcome.candidate_verifications.
                        push_back(candidate);

                    if (candidate.formalization) {
                        attempts +=
                            candidate.formalization->
                                search.attempts.size();
                    }

                    if (skill_ledger_ != nullptr &&
                        outcome.last_imagination) {
                        const auto idea =
                            std::find_if(
                                outcome.last_imagination->
                                    shortlisted.begin(),
                                outcome.last_imagination->
                                    shortlisted.end(),
                                [&](const imagination::
                                        IdeaCandidate& item) {
                                    return item.idea_id ==
                                           candidate.idea_id;
                                });

                        if (idea !=
                                outcome.last_imagination->
                                    shortlisted.end() &&
                            !idea->skill_id.empty()) {
                            skill_ledger_->record_downstream(
                                idea->skill_id,
                                candidate.proven());
                        }
                    }

                    if (!candidate.proven()) {
                        continue;
                    }

                    ++verified_count;
                    verified_helpers.
                        push_back(candidate);

                    append_unique(
                        helper_context,
                        *candidate.formalization->
                            lean_declaration);

                    outcome.consolidations.push_back(
                        consolidator_.consolidate(
                            problem.episode_id,
                            problem.focus_theorem.
                                    empty()
                                ? target_name
                                : problem.
                                      focus_theorem,
                            candidate));
                }

                update_helper_success_sensors(
                    problem.sensors,
                    verified_count);

                ResearchObservation observation;
                observation.verified_candidate_lemmas =
                    verified_count;
                observation.candidate_verification_failed =
                    verified_count == 0U;
                observation.usage_delta.model_calls =
                    verifications.size();
                observation.usage_delta.proof_attempts =
                    attempts;
                observation.resource_pressure =
                    conservative_resource_pressure(
                        problem.sensors);

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::Decompose: {
                auto tree =
                    lemma_factory_.solve(
                        problem.target);

                const auto declarations =
                    tree.proof_declarations();

                for (const auto& declaration :
                     declarations) {
                    append_unique(
                        helper_context,
                        declaration);
                }

                std::vector<CandidateVerification>
                    child_candidates;
                collect_proven_child_candidates(
                    tree,
                    false,
                    child_candidates);

                for (const auto& candidate :
                     child_candidates) {
                    verified_helpers.
                        push_back(candidate);
                    outcome.candidate_verifications.
                        push_back(candidate);

                    outcome.consolidations.push_back(
                        consolidator_.consolidate(
                            problem.episode_id,
                            problem.focus_theorem.
                                    empty()
                                ? target_name
                                : problem.
                                      focus_theorem,
                            candidate));
                }

                ResearchObservation observation;
                observation.usage_delta.proof_attempts =
                    lemma_tree_attempts(
                        tree);
                observation.usage_delta.generated_lemmas =
                    tree.node_count() > 0U
                        ? tree.node_count() - 1U
                        : 0U;
                observation.resource_pressure =
                    conservative_resource_pressure(
                        problem.sensors);

                if (tree.proven()) {
                    outcome.target_result =
                        *tree.proven_result();
                    observation.lean_verified =
                        true;
                } else {
                    const std::size_t proven_children =
                        child_candidates.size();

                    update_helper_success_sensors(
                        problem.sensors,
                        proven_children);

                    observation.decomposition_complete =
                        true;
                    observation.proven_child_lemmas =
                        proven_children;
                }

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::RetryParent: {
                auto retry =
                    formalize(
                        problem.target,
                        searcher_,
                        helper_context);

                ResearchObservation observation;
                observation.usage_delta.proof_attempts =
                    proof_attempts(retry);
                observation.resource_pressure =
                    conservative_resource_pressure(
                        problem.sensors);

                if (retry.proven()) {
                    outcome.target_result =
                        retry;
                    observation.lean_verified =
                        true;
                } else {
                    update_failure_sensors(
                        problem.sensors,
                        retry.search.attempts.size(),
                        problem.logic);
                    observation.parent_retry_failed =
                        true;
                }

                transition =
                    machine.step(
                        observation);
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::Consolidate: {
                if (!outcome.target_result ||
                    !outcome.target_result->
                        proven()) {
                    throw std::logic_error(
                        "research entered consolidation without verified target");
                }

                const auto target_verified =
                    target_candidate(
                        problem.target,
                        *outcome.target_result);

                outcome.consolidations.push_back(
                    consolidator_.consolidate(
                        problem.episode_id,
                        problem.focus_theorem,
                        target_verified));

                // Now that the target exists in the theorem graph, repeat
                // helper consolidation only to establish missing USES links.
                for (const auto& helper :
                     verified_helpers) {
                    outcome.consolidations.push_back(
                        consolidator_.consolidate(
                            problem.episode_id,
                            target_name,
                            helper));
                }

                outcome.target_verified =
                    true;

                transition =
                    machine.step(
                        ResearchObservation{});
                append_transition(
                    episode_ledger_,
                    problem.episode_id,
                    transition,
                    machine.state());
                break;
            }

            case ResearchPhase::Complete:
            case ResearchPhase::Exhausted:
                break;
        }
    }

    outcome.final_state =
        machine.state();

    if (!outcome.final_state.completed &&
        !outcome.final_state.exhausted) {
        throw std::runtime_error(
            "research engine exceeded dispatch-step guard before terminal state");
    }

    if (route_memory_ != nullptr &&
        outcome.dispatched_route.has_value()) {
        const auto& usage =
            outcome.final_state.usage;
        const auto& budget =
            config_.budget;

        const auto ratio = [](
            std::size_t used,
            std::size_t maximum) {
            if (maximum == 0U) return 1.0;
            return std::min(
                1.0,
                static_cast<double>(used) /
                    static_cast<double>(maximum));
        };

        const double resource_cost =
            0.25 * (
                ratio(
                    usage.model_calls,
                    budget.max_model_calls) +
                ratio(
                    usage.proof_attempts,
                    budget.max_proof_attempts) +
                ratio(
                    usage.generated_ideas,
                    budget.max_generated_ideas) +
                ratio(
                    usage.generated_lemmas,
                    budget.max_generated_lemmas));

        bool helper_verified =
            !outcome.helper_declarations.empty();

        if (!helper_verified) {
            for (const auto& candidate :
                 outcome.candidate_verifications) {
                if (candidate.formalization.has_value() &&
                    candidate.formalization->proven()) {
                    helper_verified = true;
                    break;
                }
            }
        }

        const bool verified_progress =
            outcome.target_verified ||
            helper_verified;

        route_memory_->record(
            RouteOutcome{
                .route_id =
                    outcome.dispatched_route->
                        route_id,
                .kind =
                    outcome.dispatched_route->
                        kind,
                .domain =
                    problem.target.domain,
                .verified_progress =
                    verified_progress,
                .target_verified =
                    outcome.target_verified,
                .dead_end_escaped =
                    verified_progress,
                .resource_cost =
                    resource_cost,
            });

        if (outcome.dispatched_sequence.has_value()) {
            route_memory_->record_sequence(
                RouteSequenceOutcome{
                    .sequence_id =
                        outcome.dispatched_sequence->
                            sequence_id,
                    .domain =
                        problem.target.domain,
                    .verified_progress =
                        verified_progress,
                    .target_verified =
                        outcome.target_verified,
                    .dead_end_escaped =
                        verified_progress,
                    .resource_cost =
                        resource_cost,
                });
        }

        bool strategy_completed = false;
        std::size_t strategy_steps_attempted = 0U;

        if (outcome.dispatched_strategy.has_value()) {
            const auto& strategy =
                *outcome.dispatched_strategy;

            for (const auto& step :
                 strategy.exemplar_sequence.steps) {
                if (strategy_step_executed(
                        step,
                        attempted_route_ids,
                        outcome.final_state)) {
                    ++strategy_steps_attempted;
                }
            }

            strategy_completed =
                !strategy.exemplar_sequence.steps.empty() &&
                strategy_steps_attempted ==
                    strategy.exemplar_sequence.steps.size();

            outcome.dispatched_strategy_steps_attempted =
                strategy_steps_attempted;
            outcome.dispatched_strategy_complete =
                strategy_completed;

            if (strategy_completed) {
                route_memory_->record_strategy(
                    ResearchStrategyOutcome{
                        .strategy_id =
                            strategy.strategy_id,
                        .signature =
                            strategy.signature,
                        .domain =
                            problem.target.domain,
                        .verified_progress =
                            verified_progress,
                        .target_verified =
                            outcome.target_verified,
                        .dead_end_escaped =
                            verified_progress,
                        .resource_cost =
                            resource_cost,
                    });
            }
        }

        std::ostringstream payload;
        payload
            << "route_id="
            << outcome.dispatched_route->
                route_id
            << "\nverified_progress="
            << (verified_progress
                    ? "true"
                    : "false")
            << "\ntarget_verified="
            << (outcome.target_verified
                    ? "true"
                    : "false")
            << "\nresource_cost="
            << resource_cost;

        (void)episode_ledger_.append(
            problem.episode_id,
            "route_outcome",
            payload.str());

        if (outcome.dispatched_sequence.has_value()) {
            std::ostringstream sequence_payload;
            sequence_payload
                << "sequence_id="
                << outcome.dispatched_sequence->
                    sequence_id
                << "\nverified_progress="
                << (verified_progress
                        ? "true"
                        : "false")
                << "\ntarget_verified="
                << (outcome.target_verified
                        ? "true"
                        : "false")
                << "\nresource_cost="
                << resource_cost;

            (void)episode_ledger_.append(
                problem.episode_id,
                "route_sequence_outcome",
                sequence_payload.str());
        }

        if (outcome.dispatched_strategy.has_value()) {
            std::ostringstream strategy_payload;
            strategy_payload
                << "strategy_id="
                << outcome.dispatched_strategy->
                    strategy_id
                << "\nsignature="
                << outcome.dispatched_strategy->
                    signature
                << "\nsteps_attempted="
                << strategy_steps_attempted
                << "\nsteps_planned="
                << outcome.dispatched_strategy->
                    exemplar_sequence.steps.size()
                << "\ncomplete="
                << (strategy_completed
                        ? "true"
                        : "false")
                << "\nverified_progress="
                << (verified_progress
                        ? "true"
                        : "false")
                << "\ntarget_verified="
                << (outcome.target_verified
                        ? "true"
                        : "false")
                << "\nresource_cost="
                << resource_cost;

            (void)episode_ledger_.append(
                problem.episode_id,
                strategy_completed
                    ? "research_strategy_outcome"
                    : "research_strategy_partial",
                strategy_payload.str());
        }
    }

    const auto verification =
        episode_ledger_.verify(
            problem.episode_id);

    if (!verification.valid) {
        throw std::runtime_error(
            "research episode lineage verification failed: " +
            verification.reason);
    }

    outcome.episode_root_hash =
        verification.root_hash;

    return outcome;
}

} // namespace expert_robot::research
