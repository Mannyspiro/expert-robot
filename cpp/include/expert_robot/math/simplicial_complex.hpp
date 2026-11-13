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

} // namespace expert_robot::math::continuum
