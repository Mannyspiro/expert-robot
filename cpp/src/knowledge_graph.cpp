#include "expert_robot/knowledge_graph.hpp"
#include "expert_robot/json_util.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace expert_robot {
namespace {

const std::set<std::string> kRelations = {
    "USES",
    "GENERALIZES",
    "SPECIALIZES",
    "IMPLIES",
    "ANALOGOUS_TO",
    "GEOMETRIC_FORM_OF",
    "ALGEBRAIC_FORM_OF",
    "REQUIRES",
    "CONTRADICTS",
};

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1U);
}

std::string upper(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::toupper(ch));
    });
    return value;
}

TheoremNode node_from_json(const std::string& object) {
    TheoremNode node{
        .name = json_util::string_field(object, "name"),
        .source = json_util::string_field(object, "source"),
        .status = json_util::string_field(object, "status"),
        .statement = json_util::string_field(object, "statement"),
        .domain = json_util::string_field(object, "domain", "unknown"),
        .tags = json_util::string_array_field(object, "tags"),
    };
    validate_theorem_node(node);
    return node;
}

TheoremEdge edge_from_json(const std::string& object) {
    TheoremEdge edge{
        .source = json_util::string_field(object, "source"),
        .relation = json_util::string_field(object, "relation"),
        .target = json_util::string_field(object, "target"),
    };
    validate_theorem_edge(edge);
    return edge;
}

void write_string_array(std::ostream& out, const std::vector<std::string>& values) {
    out << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ", ";
        out << "\"" << json_util::escape(values[i]) << "\"";
    }
    out << "]";
}

} // namespace

bool TheoremEdge::operator<(const TheoremEdge& other) const noexcept {
    return std::tie(source, relation, target) <
           std::tie(other.source, other.relation, other.target);
}

bool valid_theorem_relation(std::string_view relation) {
    return kRelations.contains(upper(std::string(relation)));
}

void validate_theorem_node(TheoremNode& node) {
    node.name = trim(std::move(node.name));
    node.source = trim(std::move(node.source));
    node.status = trim(std::move(node.status));
    node.statement = trim(std::move(node.statement));
    node.domain = trim(std::move(node.domain));
    if (node.domain.empty()) node.domain = "unknown";

    if (node.name.empty()) throw std::invalid_argument("theorem name must be non-empty");
    if (node.source.empty()) throw std::invalid_argument(node.name + ": source must be non-empty");
    if (node.status.empty()) throw std::invalid_argument(node.name + ": status must be non-empty");

    for (auto& tag : node.tags) tag = trim(std::move(tag));
    node.tags.erase(
        std::remove_if(node.tags.begin(), node.tags.end(), [](const std::string& x) { return x.empty(); }),
        node.tags.end());
    std::sort(node.tags.begin(), node.tags.end());
    node.tags.erase(std::unique(node.tags.begin(), node.tags.end()), node.tags.end());
}

void validate_theorem_edge(TheoremEdge& edge) {
    edge.source = trim(std::move(edge.source));
    edge.relation = upper(trim(std::move(edge.relation)));
    edge.target = trim(std::move(edge.target));
    if (!valid_theorem_relation(edge.relation)) {
        throw std::invalid_argument("unsupported theorem relation: " + edge.relation);
    }
    if (edge.source.empty() || edge.target.empty()) {
        throw std::invalid_argument("theorem edge source and target must be non-empty");
    }
}

KnowledgeGraph::KnowledgeGraph(
    std::vector<TheoremNode> nodes,
    std::vector<TheoremEdge> edges) {
    for (auto& node : nodes) add_node(std::move(node));
    for (auto& edge : edges) add_edge(std::move(edge));
}

KnowledgeGraph KnowledgeGraph::load(const std::filesystem::path& path) {
    const std::string json = json_util::read_file(path.string());
    if (json_util::int_field(json, "schema_version", -1) != 1) {
        throw std::invalid_argument("unsupported theorem graph schema_version");
    }

    std::vector<TheoremNode> nodes;
    for (const auto& object : json_util::object_array(json, "nodes")) {
        nodes.push_back(node_from_json(object));
    }
    std::vector<TheoremEdge> edges;
    for (const auto& object : json_util::object_array(json, "edges")) {
        edges.push_back(edge_from_json(object));
    }
    return KnowledgeGraph(std::move(nodes), std::move(edges));
}

void KnowledgeGraph::add_node(TheoremNode node) {
    validate_theorem_node(node);
    const auto it = std::find_if(nodes_.begin(), nodes_.end(), [&](const TheoremNode& current) {
        return current.name == node.name;
    });
    if (it != nodes_.end()) {
        if (*it != node) throw std::invalid_argument("conflicting theorem node: " + node.name);
        return;
    }
    nodes_.push_back(std::move(node));
}

void KnowledgeGraph::upsert_node(TheoremNode node) {
    validate_theorem_node(node);
    const auto it = std::find_if(nodes_.begin(), nodes_.end(), [&](const TheoremNode& current) {
        return current.name == node.name;
    });
    if (it == nodes_.end()) nodes_.push_back(std::move(node));
    else *it = std::move(node);
}

void KnowledgeGraph::add_edge(TheoremEdge edge) {
    validate_theorem_edge(edge);
    const auto has_node = [&](const std::string& name) {
        return std::any_of(nodes_.begin(), nodes_.end(), [&](const TheoremNode& node) {
            return node.name == name;
        });
    };
    if (!has_node(edge.source)) {
        throw std::invalid_argument("edge source is not registered: " + edge.source);
    }
    if (!has_node(edge.target)) {
        throw std::invalid_argument("edge target is not registered: " + edge.target);
    }
    edges_.insert(std::move(edge));
}

const TheoremNode& KnowledgeGraph::get(std::string_view name) const {
    const auto it = std::find_if(nodes_.begin(), nodes_.end(), [&](const TheoremNode& node) {
        return node.name == name;
    });
    if (it == nodes_.end()) throw std::out_of_range("unknown theorem: " + std::string(name));
    return *it;
}

std::vector<TheoremNode> KnowledgeGraph::nodes() const {
    auto result = nodes_;
    std::sort(result.begin(), result.end(), [](const TheoremNode& a, const TheoremNode& b) {
        return a.name < b.name;
    });
    return result;
}

std::vector<TheoremEdge> KnowledgeGraph::edges() const {
    return {edges_.begin(), edges_.end()};
}

std::vector<TheoremEdge> KnowledgeGraph::related(
    std::string_view name,
    std::string_view relation) const {
    const std::string relation_norm =
        relation.empty() ? std::string{} : upper(std::string(relation));
    std::vector<TheoremEdge> result;
    for (const auto& edge : edges_) {
        const bool touches = edge.source == name || edge.target == name;
        const bool relation_matches =
            relation_norm.empty() || edge.relation == relation_norm;
        if (touches && relation_matches) result.push_back(edge);
    }
    return result;
}

void KnowledgeGraph::sync_formal_registry(const std::filesystem::path& path) {
    const std::string json = json_util::read_file(path.string());
    if (json_util::int_field(json, "schema_version", -1) != 1) {
        throw std::invalid_argument("unsupported theorem registry schema_version");
    }

    for (const auto& object : json_util::object_array(json, "theorems")) {
        const std::string name = json_util::string_field(object, "name");
        const std::string source = json_util::string_field(object, "source");
        const std::string status = json_util::string_field(object, "status", "candidate");

        std::string statement;
        std::string domain = "unknown";
        std::vector<std::string> tags;
        const auto it = std::find_if(nodes_.begin(), nodes_.end(), [&](const TheoremNode& node) {
            return node.name == name;
        });
        if (it != nodes_.end()) {
            statement = it->statement;
            domain = it->domain;
            tags = it->tags;
        }
        upsert_node(TheoremNode{
            .name = name,
            .source = source,
            .status = status,
            .statement = statement,
            .domain = domain,
            .tags = std::move(tags),
        });
    }
}

void KnowledgeGraph::save(const std::filesystem::path& path) const {
    if (!path.parent_path().empty()) std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path, std::ios::binary | std::ios::trunc);
    if (!out) throw std::runtime_error("cannot save theorem graph");

    out << "{\n  \"schema_version\": 1,\n  \"nodes\": [";
    const auto ordered_nodes = nodes();
    for (std::size_t i = 0; i < ordered_nodes.size(); ++i) {
        const auto& node = ordered_nodes[i];
        out << (i ? ",\n" : "\n")
            << "    {\n"
            << "      \"domain\": \"" << json_util::escape(node.domain) << "\",\n"
            << "      \"name\": \"" << json_util::escape(node.name) << "\",\n"
            << "      \"source\": \"" << json_util::escape(node.source) << "\",\n"
            << "      \"statement\": \"" << json_util::escape(node.statement) << "\",\n"
            << "      \"status\": \"" << json_util::escape(node.status) << "\",\n"
            << "      \"tags\": ";
        write_string_array(out, node.tags);
        out << "\n    }";
    }
    out << "\n  ],\n  \"edges\": [";

    const auto ordered_edges = edges();
    for (std::size_t i = 0; i < ordered_edges.size(); ++i) {
        const auto& edge = ordered_edges[i];
        out << (i ? ",\n" : "\n")
            << "    {\n"
            << "      \"relation\": \"" << json_util::escape(edge.relation) << "\",\n"
            << "      \"source\": \"" << json_util::escape(edge.source) << "\",\n"
            << "      \"target\": \"" << json_util::escape(edge.target) << "\"\n"
            << "    }";
    }
    out << "\n  ]\n}\n";
}

} // namespace expert_robot
