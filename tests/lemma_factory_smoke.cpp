#include "expert_robot/cognition/lemma_factory_bridge.hpp"
#include "expert_robot/lemma_factory.hpp"

#include <cassert>
#include <string>
#include <string_view>
#include <vector>

namespace {

class ContextAwareSearcher final : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        using namespace expert_robot;

        SearchResult result;
        result.problem = problem;

        const bool helper_goal =
            problem.statement.find(": x = x") != std::string::npos;
        const bool direct_goal =
            problem.statement.find(": True") != std::string::npos;

        bool has_helper_context = false;
        for (const auto& declaration : problem.context_declarations) {
            if (declaration.find("MathAI.Generated.helper") != std::string::npos) {
                has_helper_context = true;
                break;
            }
        }

        const bool parent_goal =
            problem.statement.find(": x + 0 = x") != std::string::npos;

        const bool success =
            direct_goal ||
            helper_goal ||
            (parent_goal && has_helper_context);

        result.attempts.push_back(SearchAttempt{
            .tactic = "simp",
            .success = success,
            .exit_code = success ? 0 : 1,
            .output = success ? "accepted" : "rejected",
        });

        if (success) {
            result.success = true;
            result.tactic = "simp";
            result.proof = "by\n  simp";
        }

        return result;
    }
};

expert_robot::FormalizationProposal parent_proposal() {
    return expert_robot::FormalizationProposal{
        .name = "parent",
        .name_space = "MathAI.Generated",
        .binders = {{"x", "ℝ"}},
        .proposition = "x + 0 = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "parent theorem",
    };
}

expert_robot::FormalizationProposal helper_proposal() {
    return expert_robot::FormalizationProposal{
        .name = "helper",
        .name_space = "MathAI.Generated",
        .binders = {{"x", "ℝ"}},
        .proposition = "x = x",
        .imports = {"MathAI"},
        .domain = "algebra",
        .rationale = "identity helper",
    };
}

class AlwaysFailSearcher final : public expert_robot::IProofSearcher {
public:
    expert_robot::SearchResult search(
        const expert_robot::SearchProblem& problem) override {
        expert_robot::SearchResult result;
        result.problem = problem;
        result.attempts.push_back(expert_robot::SearchAttempt{
            .tactic = "simp",
            .success = false,
            .exit_code = 1,
            .output = "no proof",
        });
        return result;
    }
};

} // namespace

int main() {
    using namespace expert_robot;

    auto parent = parent_proposal();
    auto helper = helper_proposal();

    assert(
        proposal_fingerprint(parent) ==
        "66345c79a780effa5a44d2794053ed35484b51824f14a888c45f7bbcdc702bfd");

    ContextAwareSearcher searcher;
    StaticLemmaDecomposer decomposer({
        {parent.qualified_name(), {helper}},
    });

    RecursiveLemmaFactory factory(
        searcher,
        decomposer,
        LemmaFactoryConfig{
            .max_depth = 3,
            .max_children = 6,
            .max_nodes = 32,
        });

    const auto solved = factory.solve(parent);
    assert(solved.status == "proven_after_children");
    assert(solved.proven());
    assert(solved.children.size() == 1);
    assert(solved.children[0].status == "proven");
    assert(solved.children[0].proven());
    assert(solved.retry_result.has_value());
    assert(solved.retry_result->proven());
    assert(solved.node_count() == 2);
    assert(solved.proven_node_count() == 2);

    const auto declarations = solved.proof_declarations();
    assert(declarations.size() == 2);
    assert(
        declarations[0].find("MathAI.Generated.helper") !=
        std::string::npos);
    assert(
        declarations[1].find("MathAI.Generated.parent") !=
        std::string::npos);

    // A theorem already provable without decomposition stays shallow.
    FormalizationProposal direct{
        .name = "direct",
        .name_space = "MathAI.Generated",
        .binders = {},
        .proposition = "True",
        .imports = {"MathAI"},
        .domain = "logic",
        .rationale = "direct proof",
    };
    const auto direct_result = factory.solve(direct);
    assert(direct_result.status == "proven");
    assert(direct_result.children.empty());

    // Active recursion-path cycles are rejected before consuming a node.
    AlwaysFailSearcher fail_searcher;
    FormalizationProposal cyclic{
        .name = "cyclic",
        .name_space = "MathAI.Generated",
        .binders = {},
        .proposition = "False",
        .imports = {"MathAI"},
        .domain = "logic",
        .rationale = "cycle test",
    };
    StaticLemmaDecomposer cyclic_decomposer({
        {cyclic.qualified_name(), {cyclic}},
    });
    RecursiveLemmaFactory cyclic_factory(
        fail_searcher,
        cyclic_decomposer,
        LemmaFactoryConfig{
            .max_depth = 3,
            .max_children = 6,
            .max_nodes = 8,
        });
    const auto cyclic_result = cyclic_factory.solve(cyclic);
    assert(cyclic_result.status == "children_insufficient");
    assert(cyclic_result.children.size() == 1);
    assert(cyclic_result.children[0].status == "cycle");

    // Depth zero permits the initial attempt but forbids decomposition.
    StaticLemmaDecomposer no_plan({});
    RecursiveLemmaFactory depth_factory(
        fail_searcher,
        no_plan,
        LemmaFactoryConfig{
            .max_depth = 0,
            .max_children = 6,
            .max_nodes = 8,
        });
    const auto depth_result = depth_factory.solve(cyclic);
    assert(depth_result.status == "depth_limit");

    // Node budget is global across the recursive solve.
    StaticLemmaDecomposer budget_decomposer({
        {cyclic.qualified_name(), {helper}},
    });
    RecursiveLemmaFactory budget_factory(
        fail_searcher,
        budget_decomposer,
        LemmaFactoryConfig{
            .max_depth = 3,
            .max_children = 6,
            .max_nodes = 1,
        });
    const auto budget_result = budget_factory.solve(cyclic);
    assert(budget_result.children.size() == 1);
    assert(budget_result.children[0].status == "node_budget");

    // Strict model-output parser accepts structured proposals and rejects
    // forbidden Lean escape hatches and duplicate lemma names.
    const std::string valid_json = R"JSON({
      "lemmas": [
        {
          "name": "helper_two",
          "namespace": "MathAI.Generated",
          "binders": [{"name": "x", "type": "ℝ"}],
          "proposition": "x = x",
          "imports": ["MathAI"],
          "domain": "algebra",
          "rationale": "identity"
        }
      ]
    })JSON";

    const auto parsed = parse_decomposition_json(valid_json, 6);
    assert(parsed.size() == 1);
    assert(parsed[0].qualified_name() == "MathAI.Generated.helper_two");

    bool forbidden_rejected = false;
    try {
        (void)parse_decomposition_json(R"JSON({
          "lemmas": [{
            "name": "bad",
            "namespace": "MathAI.Generated",
            "binders": [],
            "proposition": "by sorry",
            "imports": ["MathAI"],
            "domain": "logic",
            "rationale": "bad"
          }]
        })JSON");
    } catch (const std::invalid_argument&) {
        forbidden_rejected = true;
    }
    assert(forbidden_rejected);

    bool duplicate_rejected = false;
    try {
        (void)parse_decomposition_json(R"JSON({
          "lemmas": [
            {
              "name": "dup",
              "namespace": "MathAI.Generated",
              "binders": [],
              "proposition": "True",
              "imports": ["MathAI"],
              "domain": "logic",
              "rationale": "first"
            },
            {
              "name": "dup",
              "namespace": "MathAI.Generated",
              "binders": [],
              "proposition": "True",
              "imports": ["MathAI"],
              "domain": "logic",
              "rationale": "second"
            }
          ]
        })JSON");
    } catch (const std::invalid_argument&) {
        duplicate_rejected = true;
    }
    assert(duplicate_rejected);

    // Cognition invokes the factory only for the decomposition action.
    expert_robot::cognition::CognitionCycle decompose_cycle;
    decompose_cycle.decision.action =
        expert_robot::cognition::CognitiveAction::DecomposeProblem;

    expert_robot::cognition::CognitionLemmaBridge bridge(factory);
    auto activation =
        bridge.run_if_selected(decompose_cycle, parent_proposal());
    assert(activation.invoked);
    assert(activation.result.has_value());
    assert(activation.result->proven());

    expert_robot::cognition::CognitionCycle explore_cycle;
    explore_cycle.decision.action =
        expert_robot::cognition::CognitiveAction::ExploreNovelRoute;

    auto skipped =
        bridge.run_if_selected(explore_cycle, parent_proposal());
    assert(!skipped.invoked);
    assert(!skipped.result.has_value());

    return 0;
}
