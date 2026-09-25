#pragma once

#include <filesystem>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace expert_robot {

struct TheoremNode {
    std::string name;
    std::string source;
    std::string status;
    std::string statement;
    std::string domain{"unknown"};
    std::vector<std::string> tags;

    bool operator==(const TheoremNode&) const = default;
};

struct TheoremEdge {
    std::string source;
    std::string relation;
    std::string target;

    bool operator==(const TheoremEdge&) const = default;
    bool operator<(const TheoremEdge& other) const noexcept;
};

struct TheoremPath {
    std::vector<std::string> nodes;
    std::vector<std::string> relations;

    [[nodiscard]] std::size_t depth() const noexcept {
        return relations.size();
    }

    bool operator==(const TheoremPath&) const = default;
};

[[nodiscard]] bool valid_theorem_relation(std::string_view relation);
void validate_theorem_node(TheoremNode& node);
void validate_theorem_edge(TheoremEdge& edge);

class KnowledgeGraph {
public:
    KnowledgeGraph() = default;
    KnowledgeGraph(std::vector<TheoremNode> nodes, std::vector<TheoremEdge> edges = {});

    [[nodiscard]] static KnowledgeGraph load(const std::filesystem::path& path);

    void add_node(TheoremNode node);
    void upsert_node(TheoremNode node);
    void add_edge(TheoremEdge edge);

    [[nodiscard]] const TheoremNode& get(std::string_view name) const;
    [[nodiscard]] std::vector<TheoremNode> nodes() const;
    [[nodiscard]] std::vector<TheoremEdge> edges() const;
    [[nodiscard]] std::vector<TheoremEdge> related(
        std::string_view name,
        std::string_view relation = {}) const;

    [[nodiscard]] std::vector<TheoremPath> bounded_paths(
        std::string_view start,
        std::size_t max_depth = 3,
        std::size_t max_paths = 12) const;

    void sync_formal_registry(const std::filesystem::path& path);
    void save(const std::filesystem::path& path) const;

private:
    std::vector<TheoremNode> nodes_;
    std::set<TheoremEdge> edges_;
};

} // namespace expert_robot
