#include "expert_robot/swarm/task.hpp"

#include <stdexcept>

namespace expert_robot::swarm {

std::string_view role_name(AgentRole role) {
    switch (role) {
        case AgentRole::Mathematician: return "mathematician";
        case AgentRole::Skeptic: return "skeptic";
        case AgentRole::LemmaProposer: return "lemma_proposer";
        case AgentRole::Analogist: return "analogist";
        case AgentRole::GeometrySpecialist: return "geometry_specialist";
        case AgentRole::Coder: return "coder";
        case AgentRole::Synthesizer: return "synthesizer";
    }
    return "unknown";
}

std::string role_system_prompt(AgentRole role) {
    const std::string invariant =
        "You are an untrusted proposal-generating specialist inside Expert Robot. "
        "Never claim that an unverified mathematical statement is proven. "
        "Do not request or assume additional filesystem, network, credential, "
        "or execution authority. Return concise useful proposals for downstream "
        "C++ validation and Lean verification. ";

    switch (role) {
        case AgentRole::Mathematician:
            return invariant +
                "Explore mathematically rigorous solution routes, invariants, "
                "definitions, and proof structures.";
        case AgentRole::Skeptic:
            return invariant +
                "Challenge assumptions, search for counterexamples, hidden "
                "conditions, invalid implications, and brittle proof steps.";
        case AgentRole::LemmaProposer:
            return invariant +
                "Propose smaller helper lemmas that can make the target theorem "
                "easier to formalize and verify.";
        case AgentRole::Analogist:
            return invariant +
                "Search for structurally related theorems, dualities, analogies, "
                "and representation changes that may unlock progress.";
        case AgentRole::GeometrySpecialist:
            return invariant +
                "Prefer exact geometric structure, coordinate-free relations, "
                "algebra-geometry translations, and formally checkable geometry.";
        case AgentRole::Coder:
            return invariant +
                "Propose implementation, debugging, testing, and optimization "
                "ideas without weakening trust boundaries.";
        case AgentRole::Synthesizer:
            return invariant +
                "Compare multiple candidate proposals, preserve disagreements, "
                "and synthesize a small set of testable next actions.";
    }
    return invariant;
}

void validate_agent_task(const AgentTask& task) {
    if (task.task_id.empty()) {
        throw std::invalid_argument("swarm task_id must be non-empty");
    }
    if (task.goal.empty()) {
        throw std::invalid_argument("swarm goal must be non-empty");
    }
    if (task.goal.size() > 65536U) {
        throw std::invalid_argument("swarm goal exceeds size limit");
    }
    if (task.context.size() > 128U) {
        throw std::invalid_argument("swarm context has too many entries");
    }
    for (const auto& item : task.context) {
        if (item.size() > 16384U) {
            throw std::invalid_argument("swarm context entry exceeds size limit");
        }
    }
}

} // namespace expert_robot::swarm
