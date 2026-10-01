#pragma once

#include "expert_robot/imagination/idea.hpp"

#include <cstddef>
#include <map>
#include <string_view>
#include <vector>

namespace expert_robot::imagination {

struct LensLess {
    bool operator()(ImaginationLens a, ImaginationLens b) const noexcept {
        return static_cast<std::size_t>(a) < static_cast<std::size_t>(b);
    }
};

class QualityDiversityArchive {
public:
    explicit QualityDiversityArchive(std::size_t capacity_per_lens = 2);

    [[nodiscard]] double novelty_score(std::string_view text) const;

    void insert(IdeaCandidate candidate);

    [[nodiscard]] std::vector<IdeaCandidate> elites(
        ImaginationLens lens) const;
    [[nodiscard]] std::vector<IdeaCandidate> all_elites() const;
    [[nodiscard]] std::size_t size() const noexcept;

private:
    std::size_t capacity_per_lens_{2};
    std::map<ImaginationLens, std::vector<IdeaCandidate>, LensLess> niches_;
};

[[nodiscard]] double textual_novelty(
    std::string_view candidate,
    const std::vector<std::string>& references);

} // namespace expert_robot::imagination
