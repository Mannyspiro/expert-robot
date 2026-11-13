#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <map>
#include <limits>
#include <iterator>
#include <stdexcept>
#include <set>
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


// Compute matrix rank over the field F_2. Boundary coefficients +1 and -1
// both become 1, so this gives exact homology over F_2 without floating-point
// tolerances or integer-overflow assumptions.
inline std::size_t rank_mod2(std::vector<std::vector<unsigned char>> matrix) {
    if (matrix.empty()) return 0;
    const std::size_t row_count = matrix.size();
    const std::size_t column_count = matrix.front().size();
    for (const auto& row : matrix) {
        if (row.size() != column_count) {
            throw std::invalid_argument("boundary matrix must be rectangular");
        }
    }

    std::size_t pivot_row = 0;
    for (std::size_t column = 0;
         column < column_count && pivot_row < row_count; ++column) {
        std::size_t selected = pivot_row;
        while (selected < row_count && (matrix[selected][column] & 1U) == 0U) {
            ++selected;
        }
        if (selected == row_count) continue;
        std::swap(matrix[pivot_row], matrix[selected]);

        for (std::size_t row = pivot_row + 1; row < row_count; ++row) {
            if ((matrix[row][column] & 1U) == 0U) continue;
            for (std::size_t c = column; c < column_count; ++c) {
                matrix[row][c] =
                    static_cast<unsigned char>((matrix[row][c] ^ matrix[pivot_row][c]) & 1U);
            }
        }
        ++pivot_row;
    }
    return pivot_row;
}


// Construct the degree-n simplicial boundary matrix over F_2. Rows are
// (n-1)-simplices and columns are n-simplices, both in canonical key order.
inline std::vector<std::vector<unsigned char>> boundary_matrix_mod2(
    const FiniteSimplicialComplex& complex, std::size_t degree) {
    if (degree == 0) return {};
    std::vector<SimplexKey> columns;
    std::vector<SimplexKey> rows;
    for (const auto& [simplex, present] : complex.simplices()) {
        (void)present;
        if (simplex.size() == degree + 1) columns.push_back(simplex);
        if (simplex.size() == degree) rows.push_back(simplex);
    }

    std::map<SimplexKey, std::size_t> row_index;
    for (std::size_t i = 0; i < rows.size(); ++i) row_index.emplace(rows[i], i);
    std::vector<std::vector<unsigned char>> matrix(
        rows.size(), std::vector<unsigned char>(columns.size(), 0));
    for (std::size_t column = 0; column < columns.size(); ++column) {
        const auto faces = boundary(OrientedSimplex{columns[column]});
        for (const auto& [face, coefficient] : faces) {
            (void)coefficient;
            const auto found = row_index.find(face);
            if (found == row_index.end()) {
                throw std::logic_error("finite complex is missing a face of one of its simplices");
            }
            matrix[found->second][column] ^= 1U;
        }
    }
    return matrix;
}


struct F2HomologyGroup {
    std::size_t degree = 0;
    std::size_t chain_dimension = 0;
    std::size_t boundary_rank = 0;
    std::size_t coboundary_rank = 0;
    std::size_t betti_number = 0;
};


// Betti numbers over F_2: dim H_n = dim C_n - rank(d_n) - rank(d_(n+1)).
// This intentionally computes field homology, not integral torsion data.
inline std::vector<F2HomologyGroup> compute_f2_homology(
    const FiniteSimplicialComplex& complex) {
    std::size_t maximum_degree = 0;
    for (const auto& [simplex, present] : complex.simplices()) {
        (void)present;
        maximum_degree = std::max(maximum_degree, simplex.size() - 1);
    }

    std::vector<F2HomologyGroup> result;
    result.reserve(maximum_degree + 1);
    for (std::size_t degree = 0; degree <= maximum_degree; ++degree) {
        std::size_t chain_dimension = 0;
        for (const auto& [simplex, present] : complex.simplices()) {
            (void)present;
            if (simplex.size() == degree + 1) ++chain_dimension;
        }
        const auto lower = boundary_matrix_mod2(complex, degree);
        const auto upper = boundary_matrix_mod2(complex, degree + 1);
        const std::size_t boundary_rank = rank_mod2(lower);
        const std::size_t coboundary_rank = rank_mod2(upper);
        if (boundary_rank + coboundary_rank > chain_dimension) {
            throw std::logic_error("boundary ranks violate the chain-complex dimension identity");
        }
        result.push_back(F2HomologyGroup{
            degree, chain_dimension, boundary_rank, coboundary_rank,
            chain_dimension - boundary_rank - coboundary_rank
        });
    }
    return result;
}


// Return a basis for the nullspace of a matrix over F_2. The caller supplies
// the column count so matrices with zero rows still retain their domain size.
inline std::vector<std::vector<unsigned char>> nullspace_basis_mod2(
    std::vector<std::vector<unsigned char>> matrix, std::size_t column_count) {
    for (const auto& row : matrix) {
        if (row.size() != column_count) {
            throw std::invalid_argument("nullspace matrix has inconsistent row width");
        }
    }
    const std::size_t row_count = matrix.size();
    std::vector<std::size_t> pivot_columns;
    std::size_t pivot_row = 0;
    for (std::size_t column = 0;
         column < column_count && pivot_row < row_count; ++column) {
        std::size_t selected = pivot_row;
        while (selected < row_count && (matrix[selected][column] & 1U) == 0U) ++selected;
        if (selected == row_count) continue;
        std::swap(matrix[pivot_row], matrix[selected]);
        for (std::size_t row = 0; row < row_count; ++row) {
            if (row == pivot_row || (matrix[row][column] & 1U) == 0U) continue;
            for (std::size_t c = column; c < column_count; ++c) {
                matrix[row][c] = static_cast<unsigned char>(
                    (matrix[row][c] ^ matrix[pivot_row][c]) & 1U);
            }
        }
        pivot_columns.push_back(column);
        ++pivot_row;
    }

    std::vector<bool> is_pivot(column_count, false);
    for (const auto column : pivot_columns) is_pivot[column] = true;
    std::vector<std::vector<unsigned char>> basis;
    for (std::size_t free_column = 0; free_column < column_count; ++free_column) {
        if (is_pivot[free_column]) continue;
        std::vector<unsigned char> vector(column_count, 0);
        vector[free_column] = 1;
        for (std::size_t row = 0; row < pivot_columns.size(); ++row) {
            vector[pivot_columns[row]] = matrix[row][free_column] & 1U;
        }
        basis.push_back(std::move(vector));
    }
    return basis;
}


// Rank of a list of F_2 vectors, each represented in the same coordinate
// space. Empty input has rank zero.
inline std::size_t vector_rank_mod2(
    const std::vector<std::vector<unsigned char>>& vectors,
    std::size_t coordinate_count) {
    std::vector<std::vector<unsigned char>> matrix(
        coordinate_count, std::vector<unsigned char>(vectors.size(), 0));
    for (std::size_t column = 0; column < vectors.size(); ++column) {
        if (vectors[column].size() != coordinate_count) {
            throw std::invalid_argument("F2 vectors have inconsistent coordinate dimensions");
        }
        for (std::size_t row = 0; row < coordinate_count; ++row) {
            matrix[row][column] = vectors[column][row] & 1U;
        }
    }
    return rank_mod2(std::move(matrix));
}


struct F2HomologyRepresentatives {
    std::size_t degree = 0;
    // Each representative is a cycle chain, and the classes form a basis
    // modulo boundaries. Coefficients are 0/1 in F_2.
    std::vector<IntegerChain> representatives;
};


// Compute explicit cycle representatives for a basis of H_n(K; F_2).
// Boundaries are inserted into the span first; a cycle is retained exactly
// when it contributes a new independent class modulo that span.
inline std::vector<F2HomologyRepresentatives> compute_f2_homology_representatives(
    const FiniteSimplicialComplex& complex) {
    std::size_t maximum_degree = 0;
    for (const auto& [simplex, present] : complex.simplices()) {
        (void)present;
        maximum_degree = std::max(maximum_degree, simplex.size() - 1);
    }

    std::vector<F2HomologyRepresentatives> result;
    result.reserve(maximum_degree + 1);
    for (std::size_t degree = 0; degree <= maximum_degree; ++degree) {
        std::vector<SimplexKey> basis_simplices;
        for (const auto& [simplex, present] : complex.simplices()) {
            (void)present;
            if (simplex.size() == degree + 1) basis_simplices.push_back(simplex);
        }
        const std::size_t dimension = basis_simplices.size();
        const auto cycles = nullspace_basis_mod2(
            boundary_matrix_mod2(complex, degree), dimension);
        const auto upper = boundary_matrix_mod2(complex, degree + 1);

        std::vector<std::vector<unsigned char>> span;
        if (!upper.empty()) {
            for (std::size_t column = 0; column < upper.front().size(); ++column) {
                std::vector<unsigned char> boundary_vector(dimension, 0);
                for (std::size_t row = 0; row < dimension; ++row) {
                    boundary_vector[row] = upper[row][column] & 1U;
                }
                span.push_back(std::move(boundary_vector));
            }
        }

        std::size_t current_rank = vector_rank_mod2(span, dimension);
        F2HomologyRepresentatives group;
        group.degree = degree;
        for (const auto& cycle : cycles) {
            auto candidate_span = span;
            candidate_span.push_back(cycle);
            const std::size_t next_rank = vector_rank_mod2(candidate_span, dimension);
            if (next_rank == current_rank) continue;

            IntegerChain representative;
            for (std::size_t i = 0; i < dimension; ++i) {
                if ((cycle[i] & 1U) != 0U) add_chain_coefficient(representative, basis_simplices[i], 1);
            }
            group.representatives.push_back(std::move(representative));
            span.push_back(cycle);
            current_rank = next_rank;
        }
        result.push_back(std::move(group));
    }
    return result;
}



// A finite filtered complex assigns a nondecreasing filtration value to every
// simplex: each face must appear no later than its cofaces. Persistent homology
// is computed over F_2 by standard left-to-right boundary-matrix reduction.
struct FilteredSimplex {
    SimplexKey simplex;
    double filtration = 0.0;
};

struct F2PersistenceInterval {
    std::size_t degree = 0;
    double birth = 0.0;
    double death = std::numeric_limits<double>::infinity();
    SimplexKey birth_simplex;
    SimplexKey death_simplex;
    [[nodiscard]] bool essential() const noexcept {
        return !std::isfinite(death);
    }
};

inline std::vector<F2PersistenceInterval> compute_f2_persistent_homology(
    const std::vector<FilteredSimplex>& filtration) {
    if (filtration.empty()) return {};
    std::map<SimplexKey, double> values;
    for (const auto& item : filtration) {
        if (item.simplex.empty() || !std::isfinite(item.filtration) ||
            std::any_of(item.simplex.begin(), item.simplex.end(),
                        [](const std::string& vertex) { return vertex.empty(); })) {
            throw std::invalid_argument("filtered simplices need valid vertices and finite filtration values");
        }
        auto [key, sign] = canonical_orientation(item.simplex);
        (void)sign;
        if (!values.emplace(std::move(key), item.filtration).second) {
            throw std::invalid_argument("filtered complex contains a duplicate simplex");
        }
    }
    for (const auto& [simplex, value] : values) {
        if (simplex.size() <= 1) continue;
        const auto faces = boundary(OrientedSimplex{simplex});
        for (const auto& [face, coefficient] : faces) {
            (void)coefficient;
            const auto found = values.find(face);
            if (found == values.end() || found->second > value) {
                throw std::invalid_argument("filtration is not closed under faces");
            }
        }
    }

    std::vector<SimplexKey> ordered;
    ordered.reserve(values.size());
    for (const auto& [simplex, value] : values) {
        (void)value;
        ordered.push_back(simplex);
    }
    std::sort(ordered.begin(), ordered.end(), [&](const SimplexKey& a, const SimplexKey& b) {
        if (values.at(a) != values.at(b)) return values.at(a) < values.at(b);
        if (a.size() != b.size()) return a.size() < b.size();
        return a < b;
    });
    std::map<SimplexKey, std::size_t> index;
    for (std::size_t i = 0; i < ordered.size(); ++i) index.emplace(ordered[i], i);

    std::map<std::size_t, std::size_t> pivot_to_column;
    std::vector<std::set<std::size_t>> reduced_columns;
    std::vector<bool> creates_class(ordered.size(), false);
    std::vector<F2PersistenceInterval> intervals;
    for (std::size_t column = 0; column < ordered.size(); ++column) {
        std::set<std::size_t> reduced;
        if (ordered[column].size() > 1) {
            const auto faces = boundary(OrientedSimplex{ordered[column]});
            for (const auto& [face, coefficient] : faces) {
                (void)coefficient;
                reduced.insert(index.at(face));
            }
        }
        while (!reduced.empty()) {
            const std::size_t low = *reduced.rbegin();
            const auto paired = pivot_to_column.find(low);
            if (paired == pivot_to_column.end()) break;
            const auto& other = reduced_columns[paired->second];
            std::set<std::size_t> merged;
            std::set_symmetric_difference(reduced.begin(), reduced.end(),
                other.begin(), other.end(), std::inserter(merged, merged.begin()));
            reduced = std::move(merged);
        }
        if (reduced.empty()) {
            creates_class[column] = true;
        } else {
            const std::size_t low = *reduced.rbegin();
            pivot_to_column.emplace(low, column);
            const std::size_t degree = ordered[low].size() - 1;
            intervals.push_back(F2PersistenceInterval{
                degree, values.at(ordered[low]), values.at(ordered[column]),
                ordered[low], ordered[column]});
        }
        reduced_columns.push_back(std::move(reduced));
    }
    for (std::size_t i = 0; i < ordered.size(); ++i) {
        if (creates_class[i] && pivot_to_column.count(i) == 0) {
            intervals.push_back(F2PersistenceInterval{
                ordered[i].size() - 1, values.at(ordered[i]),
                std::numeric_limits<double>::infinity(), ordered[i], {}});
        }
    }
    std::sort(intervals.begin(), intervals.end(), [](const auto& a, const auto& b) {
        if (a.degree != b.degree) return a.degree < b.degree;
        if (a.birth != b.birth) return a.birth < b.birth;
        if (a.death != b.death) return a.death < b.death;
        return a.birth_simplex < b.birth_simplex;
    });
    return intervals;
}

} // namespace expert_robot::math::continuum
