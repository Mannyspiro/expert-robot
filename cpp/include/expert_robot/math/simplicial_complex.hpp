#pragma once

#include <algorithm>
#include <cstddef>
#include <map>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace expert_robot::math::continuum {

using SimplexKey = std::vector<std::string>;
using IntegerChain = std::map<SimplexKey, int>;

struct OrientedSimplex {
    // Vertex order carries orientation. Reordering vertices can change sign.
    SimplexKey vertices;
};

inline void validate_simplex(const OrientedSimplex& simplex) {
    if (simplex.vertices.size() < 2) {
        throw std::invalid_argument("a boundary operator requires a simplex of dimension >= 1");
    }
    SimplexKey sorted = simplex.vertices;
    for (const auto& vertex : sorted) {
        if (vertex.empty()) {
            throw std::invalid_argument("simplex vertex identifiers must be non-empty");
        }
    }
    std::sort(sorted.begin(), sorted.end());
    if (std::adjacent_find(sorted.begin(), sorted.end()) != sorted.end()) {
        throw std::invalid_argument("simplex vertex identifiers must be unique");
    }
}

// Return the lexicographically ordered key and the sign of the permutation
// from the supplied orientation to that canonical orientation.
inline std::pair<SimplexKey, int> canonical_orientation(SimplexKey vertices) {
    SimplexKey sorted = vertices;
    std::sort(sorted.begin(), sorted.end());
    int inversions = 0;
    for (std::size_t i = 0; i < vertices.size(); ++i) {
        for (std::size_t j = i + 1; j < vertices.size(); ++j) {
            if (vertices[i] > vertices[j]) ++inversions;
        }
    }
    return {std::move(sorted), (inversions % 2 == 0) ? 1 : -1};
}

inline void add_chain_coefficient(IntegerChain& chain,
                                  const SimplexKey& key,
                                  int coefficient) {
    if (coefficient == 0) return;
    int& total = chain[key];
    total += coefficient;
    if (total == 0) chain.erase(key);
}

// Alternating face sum: d[v0,...,vn] = sum_i (-1)^i
// [v0,...,v(i-1),v(i+1),...,vn].
inline IntegerChain boundary(const OrientedSimplex& simplex) {
    validate_simplex(simplex);
    IntegerChain result;
    for (std::size_t omitted = 0; omitted < simplex.vertices.size(); ++omitted) {
        SimplexKey face;
        face.reserve(simplex.vertices.size() - 1);
        for (std::size_t i = 0; i < simplex.vertices.size(); ++i) {
            if (i != omitted) face.push_back(simplex.vertices[i]);
        }
        auto [key, orientation_sign] = canonical_orientation(std::move(face));
        const int alternating_sign = (omitted % 2 == 0) ? 1 : -1;
        add_chain_coefficient(result, key, alternating_sign * orientation_sign);
    }
    return result;
}

// Extend the boundary operator linearly to a finite integer chain. Chain keys
// are canonical orientations, so their coefficient signs are already encoded.
inline IntegerChain boundary(const IntegerChain& chain) {
    IntegerChain result;
    for (const auto& [vertices, coefficient] : chain) {
        if (vertices.size() < 2) {
            throw std::invalid_argument("cannot take the boundary of a 0-chain");
        }
        if (!std::is_sorted(vertices.begin(), vertices.end()) ||
            std::adjacent_find(vertices.begin(), vertices.end()) != vertices.end() ||
            std::any_of(vertices.begin(), vertices.end(),
                        [](const std::string& vertex) { return vertex.empty(); })) {
            throw std::invalid_argument("chain keys must be valid canonical simplex orientations");
        }
        const IntegerChain faces = boundary(OrientedSimplex{vertices});
        for (const auto& [face, face_coefficient] : faces) {
            add_chain_coefficient(result, face, coefficient * face_coefficient);
        }
    }
    return result;
}

inline IntegerChain boundary_squared(const OrientedSimplex& simplex) {
    if (simplex.vertices.size() < 3) {
        throw std::invalid_argument("boundary squared requires a simplex of dimension >= 2");
    }
    return boundary(boundary(simplex));
}

inline bool is_zero_chain(const IntegerChain& chain) noexcept {
    return chain.empty();
}


// A degree-indexed finite simplicial chain. Every basis simplex in C_n has
// exactly n+1 vertices; the boundary map returns an element of C_(n-1).
class SimplicialChain {
public:
    SimplicialChain(std::size_t degree, IntegerChain terms)
        : degree_(degree), terms_(std::move(terms)) {
        for (const auto& [vertices, coefficient] : terms_) {
            if (coefficient == 0 || vertices.size() != degree_ + 1 ||
                !std::is_sorted(vertices.begin(), vertices.end()) ||
                std::adjacent_find(vertices.begin(), vertices.end()) != vertices.end() ||
                std::any_of(vertices.begin(), vertices.end(),
                            [](const std::string& vertex) { return vertex.empty(); })) {
                throw std::invalid_argument(
                    "chain terms must be nonzero canonical simplices of the declared degree");
            }
        }
    }

    [[nodiscard]] std::size_t degree() const noexcept { return degree_; }
    [[nodiscard]] const IntegerChain& terms() const noexcept { return terms_; }

private:
    std::size_t degree_;
    IntegerChain terms_;
};

inline SimplicialChain boundary(const SimplicialChain& chain) {
    if (chain.degree() == 0) {
        throw std::invalid_argument("the boundary of a 0-chain is not defined in this chain model");
    }
    return SimplicialChain(chain.degree() - 1, boundary(chain.terms()));
}

inline SimplicialChain boundary_squared(const SimplicialChain& chain) {
    if (chain.degree() < 2) {
        throw std::invalid_argument("boundary squared requires a chain in degree >= 2");
    }
    return boundary(boundary(chain));
}


// A vertex map induces a degree-preserving map on normalized simplicial
// chains. A simplex whose image repeats a vertex is degenerate and maps to
// zero; otherwise its image orientation is canonicalized with the appropriate
// permutation sign. The caller is responsible for ensuring that nondegenerate
// image simplices belong to the intended target complex.
class SimplicialVertexMap {
public:
    explicit SimplicialVertexMap(std::map<std::string, std::string> images)
        : images_(std::move(images)) {
        for (const auto& [source, target] : images_) {
            if (source.empty() || target.empty()) {
                throw std::invalid_argument("vertex-map identifiers must be non-empty");
            }
        }
    }

    [[nodiscard]] const std::map<std::string, std::string>& images() const noexcept {
        return images_;
    }

    [[nodiscard]] std::string operator()(const std::string& source_vertex) const {
        const auto found = images_.find(source_vertex);
        if (found == images_.end()) {
            throw std::invalid_argument("vertex map is undefined on a source vertex");
        }
        return found->second;
    }

    [[nodiscard]] SimplicialChain apply(const SimplicialChain& chain) const {
        IntegerChain mapped;
        for (const auto& [vertices, coefficient] : chain.terms()) {
            SimplexKey image_vertices;
            image_vertices.reserve(vertices.size());
            for (const auto& vertex : vertices) {
                image_vertices.push_back((*this)(vertex));
            }

            SimplexKey distinct = image_vertices;
            std::sort(distinct.begin(), distinct.end());
            if (std::adjacent_find(distinct.begin(), distinct.end()) != distinct.end()) {
                // Degenerate simplex: zero in the normalized chain group.
                continue;
            }

            auto [key, orientation_sign] = canonical_orientation(std::move(image_vertices));
            add_chain_coefficient(mapped, key, coefficient * orientation_sign);
        }
        return SimplicialChain(chain.degree(), std::move(mapped));
    }

    // For positive-degree chains, verify the chain-map identity
    // boundary(f(c)) = f(boundary(c)).
    [[nodiscard]] bool commutes_with_boundary(const SimplicialChain& chain) const {
        if (chain.degree() == 0) {
            throw std::invalid_argument(
                "chain-map boundary check requires a chain in positive degree");
        }
        return boundary(apply(chain)).terms() == apply(boundary(chain)).terms();
    }

private:
    std::map<std::string, std::string> images_;
};


// A finite abstract simplicial complex represented by its complete set of
// non-empty faces. Construction accepts maximal simplices and closes them
// under taking non-empty subsets.
class FiniteSimplicialComplex {
public:
    FiniteSimplicialComplex(std::string id, std::vector<SimplexKey> maximal_simplices)
        : id_(std::move(id)) {
        if (id_.empty()) {
            throw std::invalid_argument("simplicial-complex identifier must be non-empty");
        }
        if (maximal_simplices.empty()) {
            throw std::invalid_argument("a finite complex needs at least one non-empty simplex");
        }
        for (auto& simplex : maximal_simplices) {
            if (simplex.empty() ||
                std::any_of(simplex.begin(), simplex.end(),
                            [](const std::string& vertex) { return vertex.empty(); })) {
                throw std::invalid_argument("maximal simplices need non-empty vertex identifiers");
            }
            auto sorted = simplex;
            std::sort(sorted.begin(), sorted.end());
            if (std::adjacent_find(sorted.begin(), sorted.end()) != sorted.end()) {
                throw std::invalid_argument("maximal simplex contains a repeated vertex");
            }
            add_faces(sorted, 0, {});
        }
    }

    [[nodiscard]] const std::string& id() const noexcept { return id_; }
    [[nodiscard]] bool contains(const SimplexKey& simplex) const {
        auto key = simplex;
        std::sort(key.begin(), key.end());
        return !key.empty() &&
            std::adjacent_find(key.begin(), key.end()) == key.end() &&
            simplices_.count(key) != 0;
    }
    [[nodiscard]] const std::map<SimplexKey, bool>& simplices() const noexcept {
        return simplices_;
    }

private:
    void add_faces(const SimplexKey& vertices, std::size_t index, SimplexKey selected) {
        if (index == vertices.size()) {
            if (!selected.empty()) simplices_.emplace(std::move(selected), true);
            return;
        }
        add_faces(vertices, index + 1, selected);
        selected.push_back(vertices[index]);
        add_faces(vertices, index + 1, std::move(selected));
    }

    std::string id_;
    std::map<SimplexKey, bool> simplices_;
};


// A checked simplicial chain map between named finite complexes. Its vertex
// assignment must send every source simplex to a target simplex or to a
// degenerate simplex (which is zero in normalized chains).
class SimplicialChainMap {
public:
    SimplicialChainMap(FiniteSimplicialComplex source,
                       FiniteSimplicialComplex target,
                       SimplicialVertexMap vertex_map)
        : source_(std::move(source)), target_(std::move(target)),
          vertex_map_(std::move(vertex_map)) {
        for (const auto& [simplex, present] : source_.simplices()) {
            (void)present;
            IntegerChain singleton{{simplex, 1}};
            const auto image = vertex_map_.apply(SimplicialChain(simplex.size() - 1,
                                                                  std::move(singleton)));
            for (const auto& [image_simplex, coefficient] : image.terms()) {
                (void)coefficient;
                if (!target_.contains(image_simplex)) {
                    throw std::invalid_argument(
                        "vertex map sends a source simplex outside the target complex");
                }
            }
        }
    }

    [[nodiscard]] const std::string& source_id() const noexcept { return source_.id(); }
    [[nodiscard]] const std::string& target_id() const noexcept { return target_.id(); }

    [[nodiscard]] bool source_contains(const SimplexKey& simplex) const {
        return source_.contains(simplex);
    }
    [[nodiscard]] bool target_contains(const SimplexKey& simplex) const {
        return target_.contains(simplex);
    }
    [[nodiscard]] const std::map<SimplexKey, bool>& source_simplices() const noexcept {
        return source_.simplices();
    }
    [[nodiscard]] const std::map<SimplexKey, bool>& target_simplices() const noexcept {
        return target_.simplices();
    }

    [[nodiscard]] SimplicialChain apply(const SimplicialChain& chain) const {
        for (const auto& [simplex, coefficient] : chain.terms()) {
            (void)coefficient;
            if (!source_.contains(simplex)) {
                throw std::invalid_argument("chain contains a simplex outside the source complex");
            }
        }
        auto image = vertex_map_.apply(chain);
        for (const auto& [simplex, coefficient] : image.terms()) {
            (void)coefficient;
            if (!target_.contains(simplex)) {
                throw std::logic_error("validated chain map produced a simplex outside its target");
            }
        }
        return image;
    }

    [[nodiscard]] bool commutes_with_boundary(const SimplicialChain& chain) const {
        if (chain.degree() == 0) {
            throw std::invalid_argument("boundary commutation requires positive degree");
        }
        return boundary(apply(chain)).terms() == apply(boundary(chain)).terms();
    }

    // Compose this map A -> B with next map B -> C.
    [[nodiscard]] SimplicialChainMap then(const SimplicialChainMap& next) const {
        if (target_.id() != next.source_.id()) {
            throw std::invalid_argument("chain-map composition has mismatched intermediate complexes");
        }
        std::map<std::string, std::string> composed;
        for (const auto& [source_vertex, ignored] : vertex_map_.images()) {
            (void)ignored;
            composed.emplace(source_vertex, next.vertex_map_(vertex_map_(source_vertex)));
        }
        return SimplicialChainMap(source_, next.target_, SimplicialVertexMap(std::move(composed)));
    }

private:
    FiniteSimplicialComplex source_;
    FiniteSimplicialComplex target_;
    SimplicialVertexMap vertex_map_;
};


// Add an integer multiple of one finite chain to another, removing zero
// coefficients so equality is representation-independent.
inline void add_scaled_chain(IntegerChain& destination,
                             const IntegerChain& source,
                             int scale) {
    for (const auto& [simplex, coefficient] : source) {
        add_chain_coefficient(destination, simplex, scale * coefficient);
    }
}


// A degree +1 chain homotopy H between two chain maps f,g : C -> D.
// Values are supplied on source basis simplices; omitted values are zero.
// The defining equation is f - g = boundary o H + H o boundary.
class SimplicialChainHomotopy {
public:
    SimplicialChainHomotopy(
        const SimplicialChainMap& f,
        const SimplicialChainMap& g,
        std::map<SimplexKey, IntegerChain> values)
        : source_id_(f.source_id()), target_id_(f.target_id()),
          source_simplices_(f.source_simplices()),
          target_simplices_(f.target_simplices()), values_(std::move(values)) {
        if (f.source_id() != g.source_id() || f.target_id() != g.target_id()) {
            throw std::invalid_argument(
                "chain homotopy requires maps with identical source and target complexes");
        }
        for (const auto& [source_simplex, image] : values_) {
            if (!f.source_contains(source_simplex) ||
                !std::is_sorted(source_simplex.begin(), source_simplex.end()) ||
                std::adjacent_find(source_simplex.begin(), source_simplex.end()) != source_simplex.end()) {
                throw std::invalid_argument("homotopy key must be a canonical simplex in the source");
            }
            const std::size_t expected_degree = source_simplex.size();
            for (const auto& [target_simplex, coefficient] : image) {
                if (coefficient == 0 || target_simplex.size() != expected_degree + 1 ||
                    !std::is_sorted(target_simplex.begin(), target_simplex.end()) ||
                    std::adjacent_find(target_simplex.begin(), target_simplex.end()) != target_simplex.end() ||
                    !f.target_contains(target_simplex)) {
                    throw std::invalid_argument(
                        "homotopy values must be nonzero target simplices one degree higher");
                }
            }
        }
    }

    [[nodiscard]] const std::string& source_id() const noexcept { return source_id_; }
    [[nodiscard]] const std::string& target_id() const noexcept { return target_id_; }

    [[nodiscard]] SimplicialChain apply(const SimplicialChain& chain) const {
        IntegerChain result;
        for (const auto& [simplex, coefficient] : chain.terms()) {
            if (source_simplices_.count(simplex) == 0) {
                throw std::invalid_argument("homotopy input contains a simplex outside the source");
            }
            const auto found = values_.find(simplex);
            if (found == values_.end()) continue;
            add_scaled_chain(result, found->second, coefficient);
        }
        for (const auto& [simplex, coefficient] : result) {
            (void)coefficient;
            if (target_simplices_.count(simplex) == 0) {
                throw std::logic_error("homotopy output contains a simplex outside the target");
            }
        }
        return SimplicialChain(chain.degree() + 1, std::move(result));
    }

    // Check f(c)-g(c) = dH(c)+H(dc) for every basis simplex in the
    // finite source complex. Checking basis simplices suffices by linearity.
    [[nodiscard]] bool verifies(const SimplicialChainMap& f,
                                const SimplicialChainMap& g) const {
        if (f.source_id() != source_id_ || g.source_id() != source_id_ ||
            f.target_id() != target_id_ || g.target_id() != target_id_) {
            return false;
        }
        for (const auto& [simplex, present] : f.source_simplices()) {
            (void)present;
            const std::size_t degree = simplex.size() - 1;
            const SimplicialChain basis(degree, IntegerChain{{simplex, 1}});
            IntegerChain lhs = f.apply(basis).terms();
            add_scaled_chain(lhs, g.apply(basis).terms(), -1);

            const auto h_basis = apply(basis);
            IntegerChain rhs = boundary(h_basis).terms();
            if (degree > 0) {
                const auto h_boundary = apply(boundary(basis));
                add_scaled_chain(rhs, h_boundary.terms(), 1);
            }
            if (lhs != rhs) return false;
        }
        return true;
    }

private:
    std::string source_id_;
    std::string target_id_;
    std::map<SimplexKey, bool> source_simplices_;
    std::map<SimplexKey, bool> target_simplices_;
    std::map<SimplexKey, IntegerChain> values_;
};

} // namespace expert_robot::math::continuum
