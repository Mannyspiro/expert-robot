#include "expert_robot/swarm/supervisor.hpp"

#include <algorithm>
#include <future>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

namespace expert_robot::swarm {

void validate_swarm_limits(const SwarmLimits& limits) {
    if (limits.max_parallel_agents == 0U) {
        throw std::invalid_argument(
            "max_parallel_agents must be positive");
    }
    if (limits.max_total_tasks == 0U) {
        throw std::invalid_argument(
            "max_total_tasks must be positive");
    }
    if (limits.max_children_per_parent == 0U) {
        throw std::invalid_argument(
            "max_children_per_parent must be positive");
    }
}

SwarmSupervisor::SwarmSupervisor(
    BackendMap backends,
    SwarmLimits limits)
    : backends_(std::move(backends)),
      limits_(limits) {
    validate_swarm_limits(limits_);
    if (backends_.empty()) {
        throw std::invalid_argument(
            "swarm supervisor requires at least one backend");
    }
    for (const auto& [role, backend] : backends_) {
        (void)role;
        if (backend == nullptr) {
            throw std::invalid_argument(
                "swarm backend pointers must be non-null");
        }
    }
}

const SwarmLimits& SwarmSupervisor::limits() const noexcept {
    return limits_;
}

ITextGenerationBackend& SwarmSupervisor::backend_for(
    AgentRole role) const {
    const auto exact = backends_.find(role);
    if (exact != backends_.end()) {
        return *exact->second;
    }

    // Allow math-oriented roles to share a single mathematician backend.
    switch (role) {
        case AgentRole::Skeptic:
        case AgentRole::LemmaProposer:
        case AgentRole::Analogist:
        case AgentRole::GeometrySpecialist:
        case AgentRole::Synthesizer: {
            const auto math = backends_.find(
                AgentRole::Mathematician);
            if (math != backends_.end()) {
                return *math->second;
            }
            break;
        }
        case AgentRole::Mathematician:
        case AgentRole::Coder:
            break;
    }

    throw std::out_of_range(
        "no backend registered for swarm role");
}

std::vector<AgentResult> SwarmSupervisor::run_batch(
    const std::vector<AgentTask>& tasks) const {
    if (tasks.size() > limits_.max_total_tasks) {
        throw std::invalid_argument(
            "swarm task count exceeds max_total_tasks");
    }

    std::unordered_map<std::string, std::size_t> child_counts;
    for (const auto& task : tasks) {
        validate_agent_task(task);
        if (task.depth > limits_.max_depth) {
            throw std::invalid_argument(
                "swarm task depth exceeds max_depth");
        }
        if (!task.parent_task_id.empty()) {
            auto& count = child_counts[task.parent_task_id];
            ++count;
            if (count > limits_.max_children_per_parent) {
                throw std::invalid_argument(
                    "swarm parent exceeds max_children_per_parent");
            }
        }
        (void)backend_for(task.role);
    }

    std::vector<AgentResult> results;
    results.reserve(tasks.size());

    // Logical roles that share one backend pointer also share one execution
    // lane. This prevents multiple simultaneous copies of the same local GGUF
    // from consuming RAM/VRAM while still allowing distinct model backends to
    // execute in parallel.
    std::unordered_map<
        ITextGenerationBackend*,
        std::shared_ptr<std::mutex>> backend_locks;
    for (const auto& task : tasks) {
        auto* backend = &backend_for(task.role);
        backend_locks.try_emplace(
            backend,
            std::make_shared<std::mutex>());
    }

    // Execute in bounded waves. Each backend invocation may spawn a local
    // llama-cli subprocess; wave size therefore bounds concurrent model
    // subprocesses and model-memory pressure.
    for (std::size_t start = 0; start < tasks.size();) {
        const std::size_t end = std::min(
            tasks.size(),
            start + limits_.max_parallel_agents);

        std::vector<std::future<AgentResult>> futures;
        futures.reserve(end - start);

        for (std::size_t i = start; i < end; ++i) {
            const AgentTask task = tasks[i];
            ITextGenerationBackend* backend =
                &backend_for(task.role);
            const auto backend_lock =
                backend_locks.at(backend);

            futures.push_back(
                std::async(
                    std::launch::async,
                    [task, backend, backend_lock]() {
                        std::scoped_lock lock(*backend_lock);
                        ModelAgent agent(
                            task.role,
                            *backend);
                        return agent.run(task);
                    }));
        }

        for (auto& future : futures) {
            results.push_back(future.get());
        }

        start = end;
    }

    return results;
}

} // namespace expert_robot::swarm
