#include "expert_robot/research/candidate_verifier.hpp"

#include <cassert>
#include <string>

namespace {

class FormalizationBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    enum class Mode {
        Valid,
        Invalid
    };

    explicit FormalizationBackend(Mode mode)
        : mode_(mode) {}

    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        if (mode_ == Mode::Invalid) {
            return {
                .ok = true,
                .exit_code = 0,
                .timed_out = false,
                .output = R"JSON({
                  "name": "bad",
                  "namespace": "MathAI.Generated",
                  "binders": [],
                  "proposition": "by sorry",
                  "imports": ["MathAI"],
                  "domain": "logic",
                  "rationale": "invalid"
                })JSON",
                .diagnostics = ""
            };
        }

        return {
            .ok = true,
            .exit_code = 0,
            .timed_out = false,
            .output = R"JSON({
              "name": "candidate_identity",
              "namespace": "MathAI.Generated",
              "binders": [
                {"name": "x", "type": "ℝ"}
              ],
              "proposition": "x = x",
              "imports": ["MathAI"],
              "domain": "algebra",
              "rationale": "A minimal helper claim extracted from the candidate mechanism."
            })JSON",
            .diagnostics = ""
        };
    }

private:
    Mode mode_;
};

class IdentitySearcher final
    : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        expert_robot::SearchResult result;
        result.problem = problem;

        const bool success =
            problem.statement.find(": x = x") !=
            std::string::npos;

        result.attempts.push_back(
            expert_robot::SearchAttempt{
                .tactic = "rfl",
                .success = success,
                .exit_code = success ? 0 : 1,
                .output =
                    success ? "accepted" : "rejected",
            });

        if (success) {
            result.success = true;
            result.tactic = "rfl";
            result.proof = "by\n  rfl";
        }

        return result;
    }
};

expert_robot::imagination::IdeaCandidate accepted_idea(
    const std::string& id) {
    return expert_robot::imagination::IdeaCandidate{
        .idea_id = id,
        .lens =
            expert_robot::imagination::ImaginationLens::Analogy,
        .source_role =
            expert_robot::swarm::AgentRole::Analogist,
        .text =
            "Reduce the target to a reflexive helper identity before lifting.",
        .novelty_score = 0.8,
        .relevance_score = 0.9,
        .quality_diversity_score = 0.85,
        .skeptic_valid = true,
        .skeptic_keep = true,
        .skeptic_risk = 20,
        .skeptic_critique =
            "Simple enough to test immediately."
    };
}

} // namespace

int main() {
    using namespace expert_robot;
    using namespace expert_robot::research;

    FormalizationBackend backend(
        FormalizationBackend::Mode::Valid);
    ModelFormalizationProposer proposer(
        backend);
    IdentitySearcher searcher;

    CandidateVerifier verifier(
        proposer,
        searcher,
        CandidateVerifierConfig{
            .max_candidates = 2
        });

    auto accepted =
        accepted_idea("abc123");

    auto rejected =
        accepted_idea("reject456");
    rejected.skeptic_keep = false;
    rejected.skeptic_risk = 90;

    auto extra =
        accepted_idea("extra789");

    const auto results =
        verifier.verify(
            "Prove the target identity.",
            "algebra",
            {accepted, rejected, extra},
            {"benchmark_case=identity"});

    assert(results.size() == 2);

    assert(
        results[0].idea_id ==
        "abc123");
    assert(
        results[0].proposal_generated);
    assert(
        results[0].proposal.has_value());
    assert(
        results[0].formalization.has_value());
    assert(
        results[0].proven());
    assert(
        results[0].formalization->
            lean_declaration.has_value());

    assert(
        results[1].idea_id ==
        "reject456");
    assert(
        !results[1].proposal_generated);
    assert(
        !results[1].proposal.has_value());
    assert(
        !results[1].formalization.has_value());
    assert(
        results[1].error ==
        "candidate did not pass skeptic gate");

    FormalizationBackend invalid_backend(
        FormalizationBackend::Mode::Invalid);
    ModelFormalizationProposer invalid_proposer(
        invalid_backend);
    CandidateVerifier invalid_verifier(
        invalid_proposer,
        searcher);

    const auto invalid_results =
        invalid_verifier.verify(
            "Prove something.",
            "logic",
            {accepted});

    assert(
        invalid_results.size() == 1);
    assert(
        !invalid_results[0].proven());
    assert(
        !invalid_results[0].error.empty());

    return 0;
}
