#include "expert_robot/imagination/controller.hpp"

#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::imagination {
namespace {

double clamp01(double x) {
    return std::clamp(x, 0.0, 1.0);
}

double action_bonus(
    ImaginationLens lens,
    cognition::CognitiveAction action) {
    using A = cognition::CognitiveAction;
    using L = ImaginationLens;

    switch (action) {
        case A::ExploreNovelRoute:
            return 0.80;
        case A::SwitchRepresentation:
            if (lens == L::Geometry ||
                lens == L::Algebra ||
                lens == L::Duality ||
                lens == L::Spectral ||
                lens == L::Topological) {
                return 1.00;
            }
            return 0.55;
        case A::DecomposeProblem:
            if (lens == L::Lemma ||
                lens == L::Simplification ||
                lens == L::Generalization ||
                lens == L::Construction) {
                return 1.00;
            }
            return 0.50;
        case A::SeekCounterexample:
            if (lens == L::Inversion ||
                lens == L::BoundaryCase ||
                lens == L::Counterfactual) {
                return 1.00;
            }
            return 0.45;
        case A::AbstractGeneralize:
            if (lens == L::Generalization ||
                lens == L::Duality ||
                lens == L::Topological ||
                lens == L::Spectral ||
                lens == L::Algebra) {
                return 1.00;
            }
            return 0.55;
        case A::CompressSimplify:
            if (lens == L::Simplification ||
                lens == L::Construction ||
                lens == L::Lemma) {
                return 1.00;
            }
            return 0.45;
        case A::IntensifyVerification:
            if (lens == L::BoundaryCase ||
                lens == L::Counterfactual ||
                lens == L::Inversion) {
                return 0.85;
            }
            return 0.35;
        case A::ContinueCurrentRoute:
            return 0.35;
        case A::ConserveCompute:
            return 0.10;
        case A::Count:
            break;
    }
    return 0.25;
}

std::string normalized_for_id(std::string text) {
    auto first = text.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    auto last = text.find_last_not_of(" \t\r\n");
    text = text.substr(first, last - first + 1U);
    return text;
}

struct SkepticVerdict {
    bool valid{false};
    bool keep{false};
    int risk{100};
    std::string critique;
};

SkepticVerdict parse_skeptic_verdict(
    const swarm::AgentResult& result) {
    if (!result.ok) return {};

    std::istringstream in(result.output);
    std::string decision_line;
    std::string risk_line;
    std::string critique_line;

    if (!std::getline(in, decision_line) ||
        !std::getline(in, risk_line)) {
        return {};
    }

    bool keep = false;
    if (decision_line == "DECISION=KEEP") {
        keep = true;
    } else if (decision_line == "DECISION=REJECT") {
        keep = false;
    } else {
        return {};
    }

    const std::string prefix = "RISK=";
    if (!risk_line.starts_with(prefix)) {
        return {};
    }

    int risk = 100;
    try {
        std::size_t consumed = 0;
        risk = std::stoi(
            risk_line.substr(prefix.size()),
            &consumed);
        if (consumed !=
            risk_line.size() - prefix.size()) {
            return {};
        }
    } catch (...) {
        return {};
    }

    if (risk < 0 || risk > 100) {
        return {};
    }

    std::string critique;
    std::string line;
    while (std::getline(in, line)) {
        if (!critique.empty()) critique.push_back('\n');
        if (line.starts_with("CRITIQUE=")) {
            critique += line.substr(9);
        } else {
            critique += line;
        }
    }

    return SkepticVerdict{
        .valid = true,
        .keep = keep,
        .risk = risk,
        .critique = std::move(critique),
    };
}

std::vector<skills::MathSkill> skills_for_lens(
    const skills::MathSkillCatalog& catalog,
    const ImaginationRequest& request,
    ImaginationLens lens) {
    auto result =
        catalog.qualified_for_lens(lens);

    if (!request.experimental_skills.empty() &&
        !request.evaluation_mode) {
        throw std::invalid_argument(
            "experimental skills require evaluation_mode");
    }

    std::set<std::string> ids;
    for (const auto& skill : result) {
        ids.insert(skill.skill_id);
    }

    for (const auto& skill :
         request.experimental_skills) {
        if (skill.stage !=
            skills::SkillStage::Experimental) {
            throw std::invalid_argument(
                "evaluation overlay accepts only experimental skills");
        }
        if (!skill.requires_lean_verification) {
            throw std::invalid_argument(
                "experimental math skill must preserve Lean verification");
        }
        if (skill.skill_id.empty() ||
            skill.title.empty() ||
            skill.procedure.empty()) {
            throw std::invalid_argument(
                "experimental skill overlay fields must be non-empty");
        }
        if (!skill.skill_id.starts_with(
                "math.experimental.")) {
            throw std::invalid_argument(
                "experimental overlay skill ID must use math.experimental.*");
        }

        if (skill.lens != lens) {
            continue;
        }

        if (!ids.insert(skill.skill_id).second) {
            throw std::invalid_argument(
                "duplicate skill ID in imagination evaluation overlay");
        }

        result.push_back(skill);
    }

    return result;
}

double smoothed_rate(
    long long successes,
    long long trials) {
    if (successes < 0 || trials < 0 ||
        successes > trials) {
        return 0.0;
    }
    return static_cast<double>(successes + 1) /
           static_cast<double>(trials + 2);
}

double skill_evidence_score(
    const skills::MathSkill& skill,
    const skills::SkillLedger* ledger) {
    const double stage_prior =
        skill.stage == skills::SkillStage::Qualified
            ? 0.50
            : 0.20;

    if (ledger == nullptr) {
        return stage_prior;
    }

    const auto stats =
        ledger->stats(skill.skill_id);

    const long long resolved =
        stats.downstream_verified +
        stats.downstream_failed;

    const double verified =
        smoothed_rate(
            stats.downstream_verified,
            resolved);
    const double shortlisted =
        smoothed_rate(
            stats.shortlisted,
            stats.attempts);
    const double skeptic =
        smoothed_rate(
            stats.skeptic_passes,
            stats.attempts);

    // New/rarely tried skills keep a small exploration bonus, but evidence
    // dominates once real downstream outcomes accumulate.
    const double exploration =
        1.0 / std::sqrt(
            static_cast<double>(
                stats.attempts + 1));

    return clamp01(
        stage_prior +
        0.25 * verified +
        0.10 * shortlisted +
        0.05 * skeptic +
        0.10 * exploration);
}

std::optional<skills::MathSkill>
select_skill_for_lens(
    const skills::MathSkillCatalog& catalog,
    const ImaginationRequest& request,
    ImaginationLens lens,
    const skills::SkillLedger* ledger) {
    auto candidates =
        skills_for_lens(
            catalog,
            request,
            lens);

    if (request.evaluation_mode) {
        std::vector<skills::MathSkill>
            experimental;
        for (const auto& skill : candidates) {
            if (skill.stage ==
                skills::SkillStage::Experimental) {
                experimental.push_back(skill);
            }
        }

        // Ablation means isolate the experimental procedure instead of
        // blending it with a qualified baseline in the same prompt.
        if (!experimental.empty()) {
            candidates =
                std::move(experimental);
        }
    }

    if (candidates.empty()) {
        return std::nullopt;
    }

    std::stable_sort(
        candidates.begin(),
        candidates.end(),
        [&](const skills::MathSkill& a,
            const skills::MathSkill& b) {
            const double sa =
                skill_evidence_score(
                    a,
                    ledger);
            const double sb =
                skill_evidence_score(
                    b,
                    ledger);
            if (sa != sb) return sa > sb;
            return a.skill_id < b.skill_id;
        });

    return candidates.front();
}

bool candidate_better(
    const IdeaCandidate& a,
    const IdeaCandidate& b) {
    const double sa = a.final_score();
    const double sb = b.final_score();
    if (sa != sb) return sa > sb;

    if (a.quality_diversity_score !=
        b.quality_diversity_score) {
        return a.quality_diversity_score >
               b.quality_diversity_score;
    }

    if (a.novelty_score != b.novelty_score) {
        return a.novelty_score >
               b.novelty_score;
    }

    return a.idea_id < b.idea_id;
}

} // namespace

void validate_imagination_config(
    const ImaginationConfig& c) {
    if (c.normal_lens_budget == 0U ||
        c.breakthrough_lens_budget == 0U ||
        c.minimum_lens_budget == 0U ||
        c.skeptic_budget == 0U ||
        c.max_expensive_candidates == 0U ||
        c.archive_capacity_per_lens == 0U) {
        throw std::invalid_argument(
            "imagination budgets and archive capacity must be positive");
    }

    if (c.normal_lens_budget >
            static_cast<std::size_t>(ImaginationLens::Count) ||
        c.breakthrough_lens_budget >
            static_cast<std::size_t>(ImaginationLens::Count) ||
        c.minimum_lens_budget >
            c.normal_lens_budget ||
        c.minimum_lens_budget >
            c.breakthrough_lens_budget) {
        throw std::invalid_argument(
            "imagination lens budget exceeds available lens count");
    }

    if (!std::isfinite(c.minimum_imagination_drive) ||
        c.minimum_imagination_drive < 0.0 ||
        c.minimum_imagination_drive > 1.0) {
        throw std::invalid_argument(
            "minimum_imagination_drive must be in [0,1]");
    }

    if (c.maximum_skeptic_risk < 0 ||
        c.maximum_skeptic_risk > 100) {
        throw std::invalid_argument(
            "maximum_skeptic_risk must be in [0,100]");
    }

    if (c.theorem_graph_max_depth == 0U ||
        c.theorem_graph_max_paths == 0U) {
        throw std::invalid_argument(
            "theorem graph imagination budgets must be positive");
    }
}

ImaginationController::ImaginationController(
    swarm::SwarmSupervisor& swarm,
    ImaginationConfig config,
    const KnowledgeGraph* theorem_graph,
    skills::MathSkillCatalog skill_catalog,
    ImaginationMemory* memory,
    skills::SkillLedger* skill_ledger)
    : swarm_(swarm),
      config_(config),
      theorem_graph_(theorem_graph),
      archive_(config.archive_capacity_per_lens),
      skills_(std::move(skill_catalog)),
      memory_(memory),
      skill_ledger_(skill_ledger) {
    validate_imagination_config(config_);

    if (memory_ != nullptr) {
        for (auto idea : memory_->all()) {
            archive_.insert(std::move(idea));
        }
    }
}

const QualityDiversityArchive&
ImaginationController::archive() const noexcept {
    return archive_;
}

double ImaginationController::imagination_drive(
    const ImaginationRequest& r) const {
    cognition::validate_personality(r.personality);
    cognition::validate_logical_assessment(r.logic);

    const double available_compute =
        1.0 - r.cognition.interoception.state.resource_pressure;

    double drive =
        0.20 * r.personality.openness +
        0.16 * r.personality.novelty_seeking +
        0.16 * r.logic.expected_information_gain +
        0.14 * r.cognition.interoception.state.stagnation +
        0.12 * r.cognition.interoception.state.novelty +
        0.10 * r.cognition.affect.exploration_drive +
        0.12 * available_compute;

    if (r.cognition.decision.breakthrough_mode) {
        drive += 0.12;
    }

    if (r.cognition.decision.action ==
        cognition::CognitiveAction::ConserveCompute) {
        drive -= 0.30;
    }

    return clamp01(drive);
}

std::size_t
ImaginationController::effective_lens_budget(
    const ImaginationRequest& request) const {
    const std::size_t base =
        request.cognition.decision.breakthrough_mode
            ? config_.breakthrough_lens_budget
            : config_.normal_lens_budget;

    if (request.cognition.decision.action ==
        cognition::CognitiveAction::ConserveCompute) {
        return config_.minimum_lens_budget;
    }

    const double pressure =
        clamp01(
            std::max(
                request.cognition.
                    interoception.state.
                    resource_pressure,
                request.cognition.
                    affect.compute_conservation));

    // Preserve full fan-out at <=25% pressure. From there, taper smoothly
    // toward the configured floor by 90% pressure.
    const double scale =
        clamp01(
            (0.90 - pressure) /
            0.65);

    const std::size_t span =
        base - config_.minimum_lens_budget;

    const auto scaled_span =
        static_cast<std::size_t>(
            std::llround(
                static_cast<double>(span) *
                scale));

    return std::clamp(
        config_.minimum_lens_budget +
            scaled_span,
        config_.minimum_lens_budget,
        base);
}

std::vector<ImaginationLens>
ImaginationController::choose_lenses(
    const ImaginationRequest& request,
    std::size_t budget) const {
    struct RankedLens {
        ImaginationLens lens;
        double score;
    };

    std::vector<RankedLens> ranked;

    for (std::size_t i = 0;
         i < static_cast<std::size_t>(ImaginationLens::Count);
         ++i) {
        const auto lens =
            static_cast<ImaginationLens>(i);

        double score =
            action_bonus(
                lens,
                request.cognition.decision.action);

        switch (lens) {
            case ImaginationLens::Analogy:
            case ImaginationLens::Duality:
                score += 0.20 * request.personality.openness;
                break;
            case ImaginationLens::Geometry:
            case ImaginationLens::Algebra:
            case ImaginationLens::Spectral:
            case ImaginationLens::Topological:
                score += 0.15 * request.personality.abstraction_bias;
                break;
            case ImaginationLens::Generalization:
                score += 0.20 * request.personality.abstraction_bias;
                break;
            case ImaginationLens::Simplification:
            case ImaginationLens::Lemma:
                score += 0.20 * request.personality.compression_drive;
                break;
            case ImaginationLens::Inversion:
            case ImaginationLens::BoundaryCase:
            case ImaginationLens::Counterfactual:
                score += 0.20 * request.personality.skepticism;
                break;
            case ImaginationLens::Construction:
                score += 0.10 * request.personality.persistence;
                break;
            case ImaginationLens::Count:
                break;
        }

        ranked.push_back({lens, score});
    }

    std::stable_sort(
        ranked.begin(),
        ranked.end(),
        [](const RankedLens& a, const RankedLens& b) {
            if (a.score != b.score) return a.score > b.score;
            return static_cast<std::size_t>(a.lens) <
                   static_cast<std::size_t>(b.lens);
        });

    budget = std::min(budget, ranked.size());

    std::vector<ImaginationLens> selected;
    selected.reserve(budget);
    for (std::size_t i = 0; i < budget; ++i) {
        selected.push_back(ranked[i].lens);
    }
    return selected;
}

std::vector<std::string>
ImaginationController::augmented_context(
    const ImaginationRequest& request) const {
    auto context = request.context;

    if (theorem_graph_ != nullptr &&
        !request.focus_theorem.empty()) {
        try {
            auto paths =
                theorem_graph_->bounded_paths(
                    request.focus_theorem,
                    config_.theorem_graph_max_depth,
                    config_.theorem_graph_max_paths);

            const auto terminal_verified =
                [&](const TheoremPath& path) {
                    if (path.nodes.empty()) return false;
                    try {
                        return theorem_graph_->
                            get(path.nodes.back()).status ==
                            "verified";
                    } catch (...) {
                        return false;
                    }
                };

            std::stable_sort(
                paths.begin(),
                paths.end(),
                [&](const TheoremPath& a,
                    const TheoremPath& b) {
                    const bool a_verified =
                        terminal_verified(a);
                    const bool b_verified =
                        terminal_verified(b);

                    if (a_verified != b_verified) {
                        return a_verified > b_verified;
                    }
                    if (a.depth() != b.depth()) {
                        return a.depth() < b.depth();
                    }
                    return a.nodes < b.nodes;
                });

            for (const auto& path : paths) {
                if (path.nodes.size() < 2U) continue;

                bool verified = false;
                std::string statement;
                std::string domain = "unknown";

                try {
                    const auto& terminal =
                        theorem_graph_->get(
                            path.nodes.back());
                    verified =
                        terminal.status == "verified";
                    statement =
                        terminal.statement;
                    domain =
                        terminal.domain;
                } catch (...) {
                    verified = false;
                }

                std::ostringstream path_text;
                path_text
                    << (verified
                            ? "verified_theorem_graph_path: "
                            : "unverified_theorem_graph_path: ");

                for (std::size_t i = 0;
                     i < path.relations.size();
                     ++i) {
                    if (i > 0U) path_text << " -> ";
                    path_text
                        << path.nodes[i]
                        << " -[" << path.relations[i] << "]-> ";
                }

                path_text << path.nodes.back();

                if (!statement.empty()) {
                    path_text
                        << " :: "
                        << statement;
                }

                path_text
                    << " [domain="
                    << domain
                    << "; trust="
                    << (verified
                            ? "verified"
                            : "unverified_candidate")
                    << (verified
                            ? ""
                            : "; inspiration_only=true")
                    << "]";

                context.push_back(
                    path_text.str());
            }
        } catch (...) {
            // Missing graph context is not a fatal imagination error.
        }
    }

    return context;
}

ImaginationRun ImaginationController::run(
    const ImaginationRequest& request) {
    if (request.request_id.empty()) {
        throw std::invalid_argument(
            "imagination request_id must be non-empty");
    }
    if (request.goal.empty()) {
        throw std::invalid_argument(
            "imagination goal must be non-empty");
    }

    if (request.experimental_skills.size() > 8U) {
        throw std::invalid_argument(
            "experimental skill overlay exceeds evaluation limit");
    }

    if (!request.experimental_skills.empty() &&
        !request.evaluation_mode) {
        throw std::invalid_argument(
            "experimental skills are forbidden outside evaluation mode");
    }

    const double drive =
        imagination_drive(request);

    ImaginationRun run;
    run.imagination_drive = drive;

    if (drive < config_.minimum_imagination_drive) {
        run.skipped = true;
        run.note =
            "imagination drive below configured threshold";
        run.archive_elites = archive_.all_elites();
        return run;
    }

    const std::size_t lens_budget =
        effective_lens_budget(request);

    run.selected_lenses =
        choose_lenses(request, lens_budget);

    const auto context =
        augmented_context(request);

    std::vector<swarm::AgentTask> tasks;
    tasks.reserve(run.selected_lenses.size());

    std::vector<std::string>
        selected_skill_ids;
    selected_skill_ids.reserve(
        run.selected_lenses.size());

    for (const auto lens : run.selected_lenses) {
        std::ostringstream goal;
        goal
            << "Original mathematical goal:\n"
            << request.goal
            << "\n\nImagination lens: "
            << lens_name(lens)
            << "\n"
            << lens_instruction(lens);

        const auto selected_skill =
            select_skill_for_lens(
                skills_,
                request,
                lens,
                skill_ledger_);

        auto role =
            role_for_lens(lens);

        if (selected_skill.has_value()) {
            const auto& skill =
                *selected_skill;

            role =
                skill.preferred_role;

            selected_skill_ids.push_back(
                skill.skill_id);

            goal
                << "\n\n"
                << (skill.stage ==
                            skills::SkillStage::Experimental
                        ? "EXPERIMENTAL SKILL UNDER ABLATION: "
                        : "Selected reusable math skill: ")
                << skill.skill_id
                << " — " << skill.title
                << "\nProcedure: "
                << skill.procedure;
        } else {
            selected_skill_ids.emplace_back();
        }

        goal
            << "\n\nGenerate exactly ONE distinct candidate idea. "
            << "Do not rank ideas. Do not claim it is proven. "
            << "State the mechanism, why it might help, and the cheapest "
            << "next falsification or verification step.";

        tasks.push_back(
            swarm::AgentTask{
                .task_id =
                    request.request_id +
                    ":imagine:" +
                    std::string(lens_name(lens)),
                .role = role,
                .goal = goal.str(),
                .context = context,
                .parent_task_id = request.request_id,
                .depth = 1,
            });
    }

    const auto results =
        swarm_.run_batch(tasks);

    std::vector<std::string> batch_texts;

    for (std::size_t i = 0;
         i < results.size() && i < run.selected_lenses.size();
         ++i) {
        const auto& result = results[i];
        if (!result.ok) continue;

        const std::string text =
            normalized_for_id(result.output);
        if (text.empty()) continue;

        const double archive_novelty =
            archive_.novelty_score(text);
        const double batch_novelty =
            textual_novelty(text, batch_texts);
        const double novelty =
            std::min(archive_novelty, batch_novelty);

        const auto lens = run.selected_lenses[i];
        const double relevance =
            clamp01(
                0.70 *
                    action_bonus(
                        lens,
                        request.cognition.decision.action) +
                0.30 *
                    request.logic.expected_information_gain);

        const double qd_score =
            clamp01(
                0.55 * novelty +
                0.25 * relevance +
                0.10 * request.cognition.affect.exploration_drive +
                0.10 * request.personality.openness);

        IdeaCandidate idea{
            .idea_id = sha256_hex(
                std::string(lens_name(lens)) +
                "\n" + text),
            .lens = lens,
            .source_role = result.role,
            .text = text,
            .skill_id =
                i < selected_skill_ids.size()
                    ? selected_skill_ids[i]
                    : std::string{},
            .novelty_score = novelty,
            .relevance_score = relevance,
            .quality_diversity_score = qd_score,
            .skeptic_valid = false,
            .skeptic_keep = false,
            .skeptic_risk = 100,
            .skeptic_critique = "",
        };

        batch_texts.push_back(text);
        archive_.insert(idea);
        if (memory_ != nullptr) {
            memory_->upsert(idea);
        }
        run.generated.push_back(std::move(idea));
    }

    std::stable_sort(
        run.generated.begin(),
        run.generated.end(),
        [](const IdeaCandidate& a,
           const IdeaCandidate& b) {
            if (a.quality_diversity_score !=
                b.quality_diversity_score) {
                return a.quality_diversity_score >
                       b.quality_diversity_score;
            }
            return a.idea_id < b.idea_id;
        });

    const std::size_t critique_count =
        std::min(
            config_.skeptic_budget,
            run.generated.size());

    std::vector<swarm::AgentTask> skeptic_tasks;
    skeptic_tasks.reserve(critique_count);

    for (std::size_t i = 0; i < critique_count; ++i) {
        const auto& idea = run.generated[i];

        std::ostringstream goal;
        goal
            << "Critique this candidate mathematical idea independently.\n"
            << "Original goal:\n" << request.goal << "\n\n"
            << "Candidate lens: " << lens_name(idea.lens) << "\n"
            << "Candidate:\n" << idea.text << "\n\n"
            << "Return exactly this format:\n"
            << "DECISION=KEEP or DECISION=REJECT\n"
            << "RISK=<integer 0 through 100>\n"
            << "CRITIQUE=<short reason>\n"
            << "KEEP means it is worth spending further verification compute, "
            << "not that it is mathematically true.";

        skeptic_tasks.push_back(
            swarm::AgentTask{
                .task_id =
                    request.request_id +
                    ":skeptic:" +
                    idea.idea_id,
                .role = swarm::AgentRole::Skeptic,
                .goal = goal.str(),
                .context = context,
                .parent_task_id = request.request_id,
                .depth = 1,
            });
    }

    const auto skeptic_results =
        swarm_.run_batch(skeptic_tasks);

    for (std::size_t i = 0;
         i < skeptic_results.size() && i < critique_count;
         ++i) {
        const auto verdict =
            parse_skeptic_verdict(skeptic_results[i]);

        auto& idea = run.generated[i];
        idea.skeptic_valid = verdict.valid;
        idea.skeptic_keep = verdict.keep;
        idea.skeptic_risk = verdict.risk;
        idea.skeptic_critique = verdict.critique;

        archive_.insert(idea);
        if (memory_ != nullptr) {
            memory_->upsert(idea);
        }
    }

    for (const auto& idea : run.generated) {
        if (!idea.skeptic_valid ||
            !idea.skeptic_keep ||
            idea.skeptic_risk >
                config_.maximum_skeptic_risk) {
            continue;
        }
        run.shortlisted.push_back(idea);
    }

    std::stable_sort(
        run.shortlisted.begin(),
        run.shortlisted.end(),
        candidate_better);

    if (run.shortlisted.size() >
        config_.max_expensive_candidates) {
        run.shortlisted.resize(
            config_.max_expensive_candidates);
    }

    if (skill_ledger_ != nullptr) {
        for (const auto& idea : run.generated) {
            const bool shortlisted =
                std::any_of(
                    run.shortlisted.begin(),
                    run.shortlisted.end(),
                    [&](const IdeaCandidate& candidate) {
                        return candidate.idea_id ==
                               idea.idea_id;
                    });

            if (!idea.skill_id.empty()) {
                skill_ledger_->record_generation(
                    idea.skill_id,
                    idea.skeptic_valid &&
                        idea.skeptic_keep,
                    shortlisted);
            }
        }
    }

    run.archive_elites =
        archive_.all_elites();

    if (run.shortlisted.empty()) {
        run.note =
            "no candidate passed the independent skeptic gate";
        return run;
    }

    if (config_.enable_synthesis) {
        std::ostringstream synthesis_goal;
        synthesis_goal
            << "Synthesize the shortlisted mathematical research ideas below.\n"
            << "Do not declare any idea true or proven. Preserve meaningful "
            << "disagreements instead of forcing consensus. Produce a compact "
            << "plan containing: (1) complementary mechanisms, (2) conflicts, "
            << "(3) cheapest discriminating experiments or Lean lemmas, and "
            << "(4) an ordered verification plan.\n\n"
            << "Original goal:\n"
            << request.goal
            << "\n\n";

        for (std::size_t i = 0;
             i < run.shortlisted.size();
             ++i) {
            const auto& idea =
                run.shortlisted[i];

            synthesis_goal
                << "Candidate " << i + 1U
                << " [" << lens_name(idea.lens) << "]\n"
                << idea.text << "\n"
                << "Skeptic risk: "
                << idea.skeptic_risk << "/100\n"
                << "Skeptic critique: "
                << idea.skeptic_critique
                << "\n\n";
        }

        const auto synthesis_results =
            swarm_.run_batch({
                swarm::AgentTask{
                    .task_id =
                        request.request_id +
                        ":synthesis",
                    .role =
                        swarm::AgentRole::Synthesizer,
                    .goal =
                        synthesis_goal.str(),
                    .context = context,
                    .parent_task_id =
                        request.request_id,
                    .depth = 1,
                }
            });

        if (!synthesis_results.empty() &&
            synthesis_results.front().ok) {
            run.synthesis_ok = true;
            run.synthesis =
                synthesis_results.front().output;
        }
    }

    return run;
}

} // namespace expert_robot::imagination
