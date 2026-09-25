#include "expert_robot/app/math_research_service.hpp"

#include <stdexcept>
#include <utility>

namespace expert_robot::app {
namespace {

std::filesystem::path state_path(
    const MathResearchServiceConfig& config,
    const char* filename) {
    return config.state_dir / filename;
}

MathResearchServiceConfig prepare_config(
    MathResearchServiceConfig config) {
    if (config.state_dir.empty()) {
        throw std::invalid_argument(
            "math research state_dir must be non-empty");
    }

    std::filesystem::create_directories(
        config.state_dir);

    if (!config.research_engine.features.theorem_graph) {
        config.theorem_registry.clear();
        config.theorem_graph_path.clear();
    }

    if (!config.theorem_graph_path.empty() &&
        !config.theorem_graph_path.
            parent_path().empty()) {
        std::filesystem::create_directories(
            config.theorem_graph_path.
                parent_path());
    }

    return config;
}


KnowledgeGraph load_graph(
    const MathResearchServiceConfig& config) {
    if (!config.theorem_graph_path.empty() &&
        std::filesystem::exists(
            config.theorem_graph_path)) {
        return KnowledgeGraph::load(
            config.theorem_graph_path);
    }
    return KnowledgeGraph{};
}

swarm::SwarmSupervisor::BackendMap
math_backends(
    ITextGenerationBackend& backend) {
    return {
        {
            swarm::AgentRole::Mathematician,
            &backend
        }
    };
}

} // namespace

MathResearchService::MathResearchService(
    ILeanRunner& lean_runner,
    ITextGenerationBackend& freeform_math_backend,
    ITextGenerationBackend& lemma_json_backend,
    ITextGenerationBackend& formalization_json_backend,
    MathResearchServiceConfig config)
    : config_(
          prepare_config(
              std::move(config))),
      lean_runner_(lean_runner),
      freeform_math_backend_(freeform_math_backend),
      lemma_json_backend_(lemma_json_backend),
      formalization_json_backend_(
          formalization_json_backend),
      proof_config_(
          load_proof_search_config(
              config_.proof_search_config)),
      proof_memory_(
          state_path(
              config_,
              "proof_memory.sqlite3")),
      searcher_(
          proof_config_.strategies,
          lean_runner_,
          proof_memory_,
          config_.research_engine.learning_writes),
      graph_(
          load_graph(config_)),
      skill_ledger_(
          state_path(
              config_,
              "skill_ledger.sqlite3")),
      imagination_memory_(
          state_path(
              config_,
              "imagination.sqlite3")),
      route_memory_(
          state_path(
              config_,
              "route_memory.sqlite3")),
      episode_ledger_(
          state_path(
              config_,
              "research_episodes.sqlite3")),
      swarm_(
          math_backends(
              freeform_math_backend_),
          config_.swarm_limits),
      imagination_(
          swarm_,
          config_.imagination,
          &graph_,
          skills::MathSkillCatalog::builtins(),
          &imagination_memory_,
          &skill_ledger_,
          config_.research_engine.learning_writes),
      lemma_decomposer_(
          lemma_json_backend_,
          ModelLemmaDecomposerConfig{
              .max_children =
                  config_.lemma_factory.
                      max_children
          }),
      lemma_factory_(
          searcher_,
          lemma_decomposer_,
          config_.lemma_factory),
      cognition_(
          config_.personality,
          config_.interoception,
          config_.neuromodulation),
      formalization_proposer_(
          formalization_json_backend_),
      candidate_verifier_(
          formalization_proposer_,
          searcher_,
          config_.candidate_verifier),
      consolidator_(
          graph_,
          &episode_ledger_,
          config_.theorem_graph_path),
      route_planner_(
          graph_,
          config_.route_planner,
          config_.research_engine.features.route_memory
              ? &route_memory_
              : nullptr),
      strategy_planner_(
          config_.strategy_planner,
          config_.research_engine.features.strategy_memory
              ? &route_memory_
              : nullptr),
      engine_(
          searcher_,
          cognition_,
          imagination_,
          lemma_factory_,
          candidate_verifier_,
          consolidator_,
          episode_ledger_,
          config_.research_engine,
          config_.research_engine.features.route_planning
              ? &route_planner_
              : nullptr,
          config_.research_engine.features.route_memory
              ? &route_memory_
              : nullptr,
          &skill_ledger_,
          config_.research_engine.features.strategy_planning
              ? &strategy_planner_
              : nullptr) {
    if (!config_.theorem_registry.empty() &&
        std::filesystem::exists(
            config_.theorem_registry)) {
        graph_.sync_formal_registry(
            config_.theorem_registry);
    }

    if (!config_.theorem_graph_path.empty()) {
        graph_.save(
            config_.theorem_graph_path);
    }
}

research::ResearchOutcome
MathResearchService::run(
    research::ResearchProblem problem) {
    return engine_.run(
        std::move(problem));
}

const KnowledgeGraph&
MathResearchService::graph() const noexcept {
    return graph_;
}

const research::RouteOutcomeLedger&
MathResearchService::route_memory() const noexcept {
    return route_memory_;
}

const skills::SkillLedger&
MathResearchService::skill_ledger() const noexcept {
    return skill_ledger_;
}

} // namespace expert_robot::app
