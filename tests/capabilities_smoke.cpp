#include "expert_robot/capabilities.hpp"

#include <cassert>
#include <stdexcept>
#include <vector>

int main() {
    using namespace expert_robot;

    CapabilityContract producer{
        .capability_id = "math.proof_search",
        .version = "1.0.0",
        .inputs = {{"goal", "lean.goal.v1", true}},
        .outputs = {{"candidate", "lean.candidate.v1", true}},
        .machine_callable = true,
        .implemented = true,
        .tests_passed = true,
        .formal_status = FormalStatus::Engineering,
        .implementation = "cpp::ProofSearch",
    };

    CapabilityContract consumer{
        .capability_id = "math.qualify",
        .version = "1.0.0",
        .inputs = {{"candidate", "lean.candidate.v1", true}},
        .outputs = {{"report", "lean.qualification.v1", true}},
        .machine_callable = true,
        .implemented = true,
        .tests_passed = true,
        .formal_status = FormalStatus::KernelVerified,
        .implementation = "lean::qualification",
    };

    CapabilityRegistry registry({producer, consumer});
    assert(registry.exposed().size() == 2);
    assert(registry.get("math.proof_search").exposed());

    const auto matches = producer.compatible_outputs_for(consumer);
    assert(matches.size() == 1);
    assert(matches[0].first == "candidate");
    assert(matches[0].second == "candidate");

    bool rejected = false;
    try {
        CapabilityContract invalid = producer;
        invalid.capability_id = "Bad ID";
        validate_capability(invalid);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    assert(rejected);

    return 0;
}
