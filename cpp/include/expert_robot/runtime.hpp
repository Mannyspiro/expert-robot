#pragma once

#include "expert_robot/protocol.hpp"

namespace expert_robot {

class Runtime {
public:
    Response handle(const Request& request) const;
};

} // namespace expert_robot
