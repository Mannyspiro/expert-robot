#pragma once

#include "expert_robot/swarm/task.hpp"
#include "expert_robot/text_generation.hpp"

#include <string>

namespace expert_robot::swarm {

class ModelAgent {
public:
    ModelAgent(
        AgentRole role,
        ITextGenerationBackend& backend);

    [[nodiscard]] AgentRole role() const noexcept;

    [[nodiscard]] AgentResult run(
        const AgentTask& task);

private:
    AgentRole role_;
    ITextGenerationBackend& backend_;
};

[[nodiscard]] std::string render_agent_user_prompt(
    const AgentTask& task);

} // namespace expert_robot::swarm
