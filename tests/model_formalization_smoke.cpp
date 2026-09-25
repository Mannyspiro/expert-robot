#include "expert_robot/formalizer.hpp"
#include "expert_robot/model_formalization_proposer.hpp"

#include <cassert>
#include <stdexcept>
#include <string>

namespace {

class FakeFormalizationBackend final
    : public expert_robot::ITextGenerationBackend {
public:
    enum class Mode {
        Valid,
        Forbidden,
        ExtraField
    };

    explicit FakeFormalizationBackend(Mode mode)
        : mode_(mode) {}

    expert_robot::TextGenerationResult generate(
        const expert_robot::TextGenerationRequest&) override {
        switch (mode_) {
            case Mode::Valid:
                return {
                    .ok = true,
                    .exit_code = 0,
                    .timed_out = false,
                    .output = R"JSON({
                      "name": "idea_identity",
                      "namespace": "MathAI.Generated",
                      "binders": [
                        {"name": "x", "type": "ℝ"}
                      ],
                      "proposition": "x = x",
                      "imports": ["MathAI"],
                      "domain": "algebra",
                      "rationale": "The informal identity maps directly to reflexive equality."
                    })JSON",
                    .diagnostics = ""
                };

            case Mode::Forbidden:
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

            case Mode::ExtraField:
                return {
                    .ok = true,
                    .exit_code = 0,
                    .timed_out = false,
                    .output = R"JSON({
                      "name": "bad_extra",
                      "namespace": "MathAI.Generated",
                      "binders": [],
                      "proposition": "True",
                      "imports": ["MathAI"],
                      "domain": "logic",
                      "rationale": "invalid",
                      "proof": "by trivial"
                    })JSON",
                    .diagnostics = ""
                };
        }

        return {};
    }

private:
    Mode mode_;
};

class ReflexiveProofSearcher final
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
                    success
                        ? "accepted"
                        : "rejected",
            });

        if (success) {
            result.success = true;
            result.tactic = "rfl";
            result.proof = "by\n  rfl";
        }

        return result;
    }
};

} // namespace

int main() {
    using namespace expert_robot;

    InformalFormalizationRequest request{
        .name_hint = "idea_identity",
        .name_space = "MathAI.Generated",
        .informal_claim =
            "For every real number x, x equals itself.",
        .domain = "algebra",
        .imports = {"MathAI"},
        .context = {
            "This candidate came from a skeptic-approved imagination route."
        }
    };

    FakeFormalizationBackend valid_backend(
        FakeFormalizationBackend::Mode::Valid);
    ModelFormalizationProposer proposer(
        valid_backend);

    const auto proposed =
        proposer.propose(request);

    assert(
        proposed.proposal.qualified_name() ==
        "MathAI.Generated.idea_identity");
    assert(
        proposed.proposal.binders.size() == 1);
    assert(
        proposed.proposal.binders[0].name ==
        "x");
    assert(
        proposed.proposal.proposition ==
        "x = x");

    ReflexiveProofSearcher searcher;
    const auto formalized =
        formalize(
            proposed.proposal,
            searcher);

    assert(formalized.proven());
    assert(
        formalized.lean_declaration.has_value());
    assert(
        formalized.lean_declaration->find(
            "MathAI.Generated.idea_identity") !=
        std::string::npos);

    FakeFormalizationBackend forbidden_backend(
        FakeFormalizationBackend::Mode::Forbidden);
    ModelFormalizationProposer forbidden(
        forbidden_backend);

    bool forbidden_rejected = false;
    try {
        (void)forbidden.propose(
            request);
    } catch (const std::invalid_argument&) {
        forbidden_rejected = true;
    }
    assert(forbidden_rejected);

    FakeFormalizationBackend extra_backend(
        FakeFormalizationBackend::Mode::ExtraField);
    ModelFormalizationProposer extra(
        extra_backend);

    bool extra_rejected = false;
    try {
        (void)extra.propose(
            request);
    } catch (const std::invalid_argument&) {
        extra_rejected = true;
    }
    assert(extra_rejected);

    return 0;
}
