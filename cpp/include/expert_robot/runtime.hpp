#pragma once

#include "expert_robot/artifact_registry.hpp"
#include "expert_robot/protocol.hpp"

#include <filesystem>

namespace expert_robot {

class Runtime {
public:
    explicit Runtime(std::filesystem::path artifact_registry_path = "state/merlin/artifacts.sqlite3");
    Response handle(const Request& request);

private:
    artifacts::ArtifactRegistry artifact_registry_;
};

} // namespace expert_robot
