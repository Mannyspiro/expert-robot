#pragma once

#include "expert_robot/imagination/idea.hpp"

#include <filesystem>
#include <vector>

struct sqlite3;

namespace expert_robot::imagination {

class ImaginationMemory {
public:
    explicit ImaginationMemory(
        std::filesystem::path path);
    ~ImaginationMemory();

    ImaginationMemory(
        const ImaginationMemory&) = delete;
    ImaginationMemory& operator=(
        const ImaginationMemory&) = delete;

    void upsert(const IdeaCandidate& idea);

    [[nodiscard]] std::vector<IdeaCandidate> all() const;
    [[nodiscard]] long long count() const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::imagination
