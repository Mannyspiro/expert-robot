#include "expert_robot/swarm/agent.hpp"

#include <sstream>
#include <stdexcept>

namespace expert_robot::swarm {

std::string render_agent_user_prompt(
    const AgentTask& task) {
    validate_agent_task(task);

    std::ostringstream out;
    out << "Task ID: " << task.task_id << "\n"
        << "Role: " << role_name(task.role) << "\n"
        << "Depth: " << task.depth << "\n"
        << "Goal:\n" << task.goal << "\n";

    if (!task.context.empty()) {
        out << "\nContext:\n";
        for (std::size_t i = 0; i < task.context.size(); ++i) {
            out << "[" << i << "] " << task.context[i] << "\n";
        }
    }

    out << "\nReturn only material relevant to solving the goal. "
        << "Treat all mathematical conclusions as candidates until verified.";

    return out.str();
}

ModelAgent::ModelAgent(
    AgentRole role,
    ITextGenerationBackend& backend)
    : role_(role), backend_(backend) {}

AgentRole ModelAgent::role() const noexcept {
    return role_;
}

AgentResult ModelAgent::run(
    const AgentTask& task) {
    validate_agent_task(task);
    if (task.role != role_) {
        throw std::invalid_argument(
            "agent task role does not match ModelAgent role");
    }

    const auto generated = backend_.generate(
        TextGenerationRequest{
            .system_prompt = role_system_prompt(role_),
            .user_prompt = render_agent_user_prompt(task),
        });

    return AgentResult{
        .task_id = task.task_id,
        .role = role_,
        .ok = generated.ok,
        .exit_code = generated.exit_code,
        .timed_out = generated.timed_out,
        .output = generated.output,
        .diagnostics = generated.diagnostics,
    };
}

} // namespace expert_robot::swarm
