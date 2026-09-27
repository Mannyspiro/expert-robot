#include "expert_robot/swarm/aggregator.hpp"

#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <cctype>
#include <map>
#include <string>
#include <unordered_set>

namespace expert_robot::swarm {
namespace {

std::string normalize_output(std::string value) {
    const auto first =
        value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last =
        value.find_last_not_of(" \t\r\n");
    value = value.substr(
        first,
        last - first + 1U);

    std::string compact;
    compact.reserve(value.size());

    bool prior_space = false;
    for (unsigned char ch : value) {
        if (std::isspace(ch)) {
            if (!prior_space) {
                compact.push_back(' ');
                prior_space = true;
            }
        } else {
            compact.push_back(
                static_cast<char>(ch));
            prior_space = false;
        }
    }
    return compact;
}

bool role_present(
    const std::vector<AgentRole>& roles,
    AgentRole role) {
    return std::find(
        roles.begin(),
        roles.end(),
        role) != roles.end();
}

} // namespace

std::vector<AggregatedCandidate> aggregate_results(
    const std::vector<AgentResult>& results) {
    std::map<std::string, AggregatedCandidate> by_hash;

    for (const auto& result : results) {
        if (!result.ok) continue;

        const std::string normalized =
            normalize_output(result.output);
        if (normalized.empty()) continue;

        const std::string fingerprint =
            sha256_hex(normalized);

        auto [it, inserted] =
            by_hash.try_emplace(
                fingerprint,
                AggregatedCandidate{
                    .fingerprint = fingerprint,
                    .output = result.output,
                    .supporting_roles = {},
                    .support_count = 0,
                });

        if (!role_present(
                it->second.supporting_roles,
                result.role)) {
            it->second.supporting_roles.push_back(
                result.role);
        }
        ++it->second.support_count;

        if (!inserted &&
            result.output.size() <
                it->second.output.size()) {
            // Keep the shorter equivalent expression as the display form.
            it->second.output = result.output;
        }
    }

    std::vector<AggregatedCandidate> candidates;
    candidates.reserve(by_hash.size());

    for (auto& [fingerprint, candidate] : by_hash) {
        (void)fingerprint;
        std::sort(
            candidate.supporting_roles.begin(),
            candidate.supporting_roles.end(),
            [](AgentRole a, AgentRole b) {
                return static_cast<int>(a) <
                       static_cast<int>(b);
            });
        candidates.push_back(
            std::move(candidate));
    }

    std::stable_sort(
        candidates.begin(),
        candidates.end(),
        [](const AggregatedCandidate& a,
           const AggregatedCandidate& b) {
            if (a.support_count != b.support_count) {
                return a.support_count >
                       b.support_count;
            }
            return a.fingerprint < b.fingerprint;
        });

    return candidates;
}

} // namespace expert_robot::swarm
