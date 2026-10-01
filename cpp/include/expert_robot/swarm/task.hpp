#pragma once

#include <cstddef>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::swarm {

enum class AgentRole {
    Mathematician,
    Skeptic,
    LemmaProposer,
    Analogist,
    GeometrySpecialist,
    Coder,
    Synthesizer,
};

struct AgentTask {
    std::string task_id;
    AgentRole role{AgentRole::Mathematician};
    std::string goal;
    std::vector<std::string> context;
    std::string parent_task_id;
    std::size_t depth{0};
};

struct AgentResult {
    std::string task_id;
    AgentRole role{AgentRole::Mathematician};
    bool ok{false};
    int exit_code{1};
    bool timed_out{false};
    std::string output;
    std::string diagnostics;
};

[[nodiscard]] std::string_view role_name(AgentRole role);
[[nodiscard]] std::string role_system_prompt(AgentRole role);
void validate_agent_task(const AgentTask& task);

} // namespace expert_robot::swarm
