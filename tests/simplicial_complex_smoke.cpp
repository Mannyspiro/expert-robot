#include "expert_robot/math/simplicial_complex.hpp"

#include <algorithm>
#include <cassert>
#include <string>
#include <vector>
#include <iostream>
#include <stdexcept>

using expert_robot::math::continuum::IntegerChain;
using expert_robot::math::continuum::OrientedSimplex;
using expert_robot::math::continuum::boundary;
using expert_robot::math::continuum::boundary_squared;
using expert_robot::math::continuum::is_zero_chain;

int main() {
    const OrientedSimplex triangle{{"A", "B", "C"}};
    const auto triangle_boundary = boundary(triangle);
    assert(triangle_boundary.size() == 3);
    assert(is_zero_chain(boundary_squared(triangle)));

    const OrientedSimplex tetrahedron{{"A", "B", "C", "D"}};
    const auto tetrahedron_boundary = boundary(tetrahedron);
    assert(tetrahedron_boundary.size() == 4);
    assert(is_zero_chain(boundary_squared(tetrahedron)));

    const OrientedSimplex reversed_triangle{{"B", "A", "C"}};
    const auto reversed_boundary = boundary(reversed_triangle);
    for (const auto& [face, coefficient] : triangle_boundary) {
        const auto found = reversed_boundary.find(face);
        assert(found != reversed_boundary.end());
        assert(found->second == -coefficient);
    }


    // Dimension-generic boundary-of-boundary checks. Exhaust every
    // orientation for simplices with 3 through 7 vertices (dimensions 2-6).
    for (std::size_t vertex_count = 3; vertex_count <= 7; ++vertex_count) {
        std::vector<std::string> vertices;
        for (std::size_t i = 0; i < vertex_count; ++i) {
            vertices.push_back("v" + std::to_string(i));
        }
        do {
            const OrientedSimplex simplex{vertices};
            assert(is_zero_chain(boundary_squared(simplex)));

            // Swapping any two vertices reverses orientation and negates
            // the complete boundary chain, not merely its vertex set.
            auto swapped = vertices;
            std::swap(swapped[0], swapped[1]);
            const auto original_boundary = boundary(simplex);
            const auto swapped_boundary = boundary(OrientedSimplex{swapped});
            assert(original_boundary.size() == swapped_boundary.size());
            for (const auto& [face, coefficient] : original_boundary) {
                const auto found = swapped_boundary.find(face);
                assert(found != swapped_boundary.end());
                assert(found->second == -coefficient);
            }
        } while (std::next_permutation(vertices.begin(), vertices.end()));
    }

    // The boundary operator is linear on finite integer chains.
    const OrientedSimplex simplex_abc{{"A", "B", "C"}};
    const OrientedSimplex simplex_bcd{{"B", "C", "D"}};
    IntegerChain combined;
    for (const auto& [face, coefficient] : boundary(simplex_abc)) {
        combined[face] += 2 * coefficient;
    }
    for (const auto& [face, coefficient] : boundary(simplex_bcd)) {
        combined[face] -= 3 * coefficient;
    }
    const auto boundary_of_combined = boundary(combined);
    IntegerChain expected;
    for (const auto& [vertex, coefficient] : boundary(boundary(simplex_abc))) {
        expected[vertex] += 2 * coefficient;
    }
    for (const auto& [vertex, coefficient] : boundary(boundary(simplex_bcd))) {
        expected[vertex] -= 3 * coefficient;
    }
    for (auto it = expected.begin(); it != expected.end();) {
        if (it->second == 0) it = expected.erase(it);
        else ++it;
    }
    assert(boundary_of_combined == expected);


    // Degree-indexed chain groups make the boundary map's type-level degree
    // reduction explicit: C2 -> C1 -> C0.
    using expert_robot::math::continuum::SimplicialChain;
    const SimplicialChain triangle_chain(2, IntegerChain{{{"A", "B", "C"}, 1}});
    const auto edge_chain = boundary(triangle_chain);
    assert(edge_chain.degree() == 1);
    const auto vertex_chain = boundary(edge_chain);
    assert(vertex_chain.degree() == 0);
    assert(is_zero_chain(boundary_squared(triangle_chain).terms()));

    bool rejected_mixed_degree_chain = false;
    try {
        (void)SimplicialChain(2, IntegerChain{
            {{"A", "B", "C"}, 1},
            {{"A", "B"}, 1}
        });
    } catch (const std::invalid_argument&) {
        rejected_mixed_degree_chain = true;
    }
    assert(rejected_mixed_degree_chain);

    bool rejected_boundary_of_zero_chain = false;
    try {
        (void)boundary(vertex_chain);
    } catch (const std::invalid_argument&) {
        rejected_boundary_of_zero_chain = true;
    }
    assert(rejected_boundary_of_zero_chain);

    bool rejected_duplicate_vertex = false;
    try {
        (void)boundary(OrientedSimplex{{"A", "B", "A"}});
    } catch (const std::invalid_argument&) {
        rejected_duplicate_vertex = true;
    }
    assert(rejected_duplicate_vertex);

    bool rejected_zero_simplex_boundary = false;
    try {
        (void)boundary(OrientedSimplex{{"A"}});
    } catch (const std::invalid_argument&) {
        rejected_zero_simplex_boundary = true;
    }
    assert(rejected_zero_simplex_boundary);

    bool rejected_noncanonical_chain = false;
    try {
        const IntegerChain malformed{{{"B", "A"}, 1}};
        (void)boundary(malformed);
    } catch (const std::invalid_argument&) {
        rejected_noncanonical_chain = true;
    }
    assert(rejected_noncanonical_chain);


    // Vertex maps induce chain maps: boundary(f(c)) == f(boundary(c)).
    using expert_robot::math::continuum::SimplicialVertexMap;
    const SimplicialVertexMap relabel({
        {"A", "X"}, {"B", "Y"}, {"C", "Z"}, {"D", "W"}
    });
    assert(relabel.commutes_with_boundary(triangle_chain));
    const auto relabeled = relabel.apply(triangle_chain);
    assert(relabeled.degree() == 2);
    assert(relabeled.terms().size() == 1);

    // A permutation of target vertices changes orientation by its sign.
    const SimplicialVertexMap reverse_map({
        {"A", "Z"}, {"B", "Y"}, {"C", "X"}
    });
    const auto reversed_image = reverse_map.apply(triangle_chain);
    assert(reversed_image.terms().size() == 1);
    assert(reversed_image.terms().begin()->first == (std::vector<std::string>{"X", "Y", "Z"}));
    assert(reversed_image.terms().begin()->second == -1);
    assert(reverse_map.commutes_with_boundary(triangle_chain));

    // Collapsing an edge makes the 2-simplex degenerate (zero), while the
    // two surviving boundary-edge images cancel exactly.
    const SimplicialVertexMap collapse_map({
        {"A", "X"}, {"B", "X"}, {"C", "Z"}
    });
    const auto collapsed_triangle = collapse_map.apply(triangle_chain);
    assert(collapsed_triangle.terms().empty());
    assert(collapse_map.commutes_with_boundary(triangle_chain));

    // A map must be defined on every vertex actually used by a chain.
    bool rejected_missing_vertex_image = false;
    try {
        const SimplicialVertexMap partial_map({{"A", "X"}, {"B", "Y"}});
        (void)partial_map.apply(triangle_chain);
    } catch (const std::invalid_argument&) {
        rejected_missing_vertex_image = true;
    }
    assert(rejected_missing_vertex_image);

    // The boundary-commutation helper is intentionally undefined for C0 in
    // this non-augmented chain model.
    bool rejected_degree_zero_chain_map_check = false;
    try {
        (void)relabel.commutes_with_boundary(vertex_chain);
    } catch (const std::invalid_argument&) {
        rejected_degree_zero_chain_map_check = true;
    }
    assert(rejected_degree_zero_chain_map_check);


    // Checked maps carry source/target complex identities and validate that
    // every nondegenerate image simplex belongs to the target complex.
    using expert_robot::math::continuum::FiniteSimplicialComplex;
    using expert_robot::math::continuum::SimplicialChainMap;
    const FiniteSimplicialComplex complex_a("A-complex", {{"A", "B", "C"}});
    const FiniteSimplicialComplex complex_b("B-complex", {{"X", "Y", "Z"}});
    const FiniteSimplicialComplex complex_c("C-complex", {{"P", "Q", "R"}});
    const SimplicialChainMap map_ab(
        complex_a, complex_b,
        SimplicialVertexMap({{"A", "X"}, {"B", "Y"}, {"C", "Z"}}));
    const SimplicialChainMap map_bc(
        complex_b, complex_c,
        SimplicialVertexMap({{"X", "P"}, {"Y", "Q"}, {"Z", "R"}}));
    assert(map_ab.source_id() == "A-complex");
    assert(map_ab.target_id() == "B-complex");
    assert(map_ab.commutes_with_boundary(triangle_chain));

    // Composition A -> B -> C remains a chain map A -> C.
    const auto map_ac = map_ab.then(map_bc);
    assert(map_ac.source_id() == "A-complex");
    assert(map_ac.target_id() == "C-complex");
    assert(map_ac.commutes_with_boundary(triangle_chain));
    const auto composed_image = map_ac.apply(triangle_chain);
    assert(composed_image.terms().size() == 1);
    assert(composed_image.terms().begin()->first ==
           (std::vector<std::string>{"P", "Q", "R"}));

    // Composition is rejected when the intermediate complex identities differ.
    bool rejected_mismatched_complex_composition = false;
    try {
        const FiniteSimplicialComplex unrelated("unrelated", {{"X", "Y", "Z"}});
        const SimplicialChainMap wrong_next(
            unrelated, complex_c,
            SimplicialVertexMap({{"X", "P"}, {"Y", "Q"}, {"Z", "R"}}));
        (void)map_ab.then(wrong_next);
    } catch (const std::invalid_argument&) {
        rejected_mismatched_complex_composition = true;
    }
    assert(rejected_mismatched_complex_composition);

    // A vertex assignment that preserves vertices and edges but maps a
    // source 2-simplex to a missing target 2-simplex is not simplicial.
    bool rejected_missing_target_face = false;
    try {
        const FiniteSimplicialComplex target_without_face(
            "edges-only", {{"X", "Y"}, {"Y", "Z"}, {"X", "Z"}});
        (void)SimplicialChainMap(
            complex_a, target_without_face,
            SimplicialVertexMap({{"A", "X"}, {"B", "Y"}, {"C", "Z"}}));
    } catch (const std::invalid_argument&) {
        rejected_missing_target_face = true;
    }
    assert(rejected_missing_target_face);

    // Applying a checked map to a chain outside its source complex is rejected.
    bool rejected_chain_outside_source = false;
    try {
        const SimplicialChain outside_chain(
            2, IntegerChain{{{"A", "B", "D"}, 1}});
        (void)map_ab.apply(outside_chain);
    } catch (const std::invalid_argument&) {
        rejected_chain_outside_source = true;
    }
    assert(rejected_chain_outside_source);


    // Chain homotopy distinguishes chain maps that differ on chains but
    // induce the same map on homology.
    using expert_robot::math::continuum::SimplicialChainHomotopy;
    const SimplicialChainMap map_constant(
        complex_a, complex_b,
        SimplicialVertexMap({{"A", "X"}, {"B", "X"}, {"C", "X"}}));
    const SimplicialChainHomotopy contraction(
        map_ab, map_constant,
        {
            {{"B"}, IntegerChain{{{"X", "Y"}, 1}}},
            {{"C"}, IntegerChain{{{"X", "Z"}, 1}}},
            {{"B", "C"}, IntegerChain{{{"X", "Y", "Z"}, 1}}}
        });
    assert(contraction.source_id() == "A-complex");
    assert(contraction.target_id() == "B-complex");
    assert(contraction.verifies(map_ab, map_constant));

    // A deliberately incomplete homotopy fails the chain-homotopy identity.
    const SimplicialChainHomotopy incomplete_contraction(
        map_ab, map_constant,
        {{{"C"}, IntegerChain{{{"X", "Z"}, 1}}}});
    assert(!incomplete_contraction.verifies(map_ab, map_constant));


    // The public H operation enforces its source domain, not only the
    // verifier's internal basis traversal.
    bool rejected_homotopy_input_outside_source = false;
    try {
        (void)contraction.apply(SimplicialChain(
            2, IntegerChain{{{"A", "B", "D"}, 1}}));
    } catch (const std::invalid_argument&) {
        rejected_homotopy_input_outside_source = true;
    }
    assert(rejected_homotopy_input_outside_source);

    // Homotopies cannot be attached to maps with different source/target pairs.
    bool rejected_homotopy_map_mismatch = false;
    try {
        (void)SimplicialChainHomotopy(map_ab, map_ac, {});
    } catch (const std::invalid_argument&) {
        rejected_homotopy_map_mismatch = true;
    }
    assert(rejected_homotopy_map_mismatch);

    // Homotopy output must be a canonical simplex in the target, one degree
    // above its source simplex.
    bool rejected_invalid_homotopy_value = false;
    try {
        (void)SimplicialChainHomotopy(
            map_ab, map_constant,
            {{{"B"}, IntegerChain{{{"X", "Y", "missing"}, 1}}}});
    } catch (const std::invalid_argument&) {
        rejected_invalid_homotopy_value = true;
    }
    assert(rejected_invalid_homotopy_value);


    // Exact finite-field homology: F_2 Betti numbers for basic spaces.
    using expert_robot::math::continuum::compute_f2_homology;
    using expert_robot::math::continuum::rank_mod2;
    const auto point_homology = compute_f2_homology(
        FiniteSimplicialComplex("one-point", {{"P"}}));
    assert(point_homology.size() == 1);
    assert(point_homology[0].degree == 0);
    assert(point_homology[0].betti_number == 1);

    const auto disconnected_homology = compute_f2_homology(
        FiniteSimplicialComplex("two-points", {{"P"}, {"Q"}}));
    assert(disconnected_homology[0].betti_number == 2);

    const auto interval_homology = compute_f2_homology(
        FiniteSimplicialComplex("interval", {{"P", "Q"}}));
    assert(interval_homology[0].betti_number == 1);
    assert(interval_homology[1].betti_number == 0);

    const auto filled_triangle_homology = compute_f2_homology(
        FiniteSimplicialComplex("filled-triangle", {{"A", "B", "C"}}));
    assert(filled_triangle_homology[0].betti_number == 1);
    assert(filled_triangle_homology[1].betti_number == 0);
    assert(filled_triangle_homology[2].betti_number == 0);

    const auto circle_homology = compute_f2_homology(
        FiniteSimplicialComplex("triangle-circle",
                                {{"A", "B"}, {"B", "C"}, {"A", "C"}}));
    assert(circle_homology[0].betti_number == 1);
    assert(circle_homology[1].betti_number == 1);

    const auto sphere_homology = compute_f2_homology(
        FiniteSimplicialComplex("tetrahedron-boundary",
                                {{"A", "B", "C"}, {"A", "B", "D"},
                                 {"A", "C", "D"}, {"B", "C", "D"}}));
    assert(sphere_homology[0].betti_number == 1);
    assert(sphere_homology[1].betti_number == 0);
    assert(sphere_homology[2].betti_number == 1);


    // Explicit F_2 homology representatives agree in count with Betti
    // numbers and are cycles under the corresponding boundary matrices.
    using expert_robot::math::continuum::compute_f2_homology_representatives;
    using expert_robot::math::continuum::boundary_matrix_mod2;
    const auto circle_representatives =
        compute_f2_homology_representatives(FiniteSimplicialComplex(
            "triangle-circle-representatives",
            {{"A", "B"}, {"B", "C"}, {"A", "C"}}));
    assert(circle_representatives[0].representatives.size() == 1);
    assert(circle_representatives[1].representatives.size() == 1);
    assert(circle_representatives[1].representatives[0].size() == 3);

    const auto sphere_representatives =
        compute_f2_homology_representatives(FiniteSimplicialComplex(
            "tetrahedron-boundary-representatives",
            {{"A", "B", "C"}, {"A", "B", "D"},
             {"A", "C", "D"}, {"B", "C", "D"}}));
    assert(sphere_representatives[0].representatives.size() == 1);
    assert(sphere_representatives[1].representatives.empty());
    assert(sphere_representatives[2].representatives.size() == 1);
    assert(sphere_representatives[2].representatives[0].size() == 4);

    const FiniteSimplicialComplex circle_complex(
        "cycle-check", {{"A", "B"}, {"B", "C"}, {"A", "C"}});
    const auto edge_boundary = boundary_matrix_mod2(circle_complex, 1);
    const auto& cycle = circle_representatives[1].representatives[0];
    std::vector<SimplexKey> edge_basis;
    for (const auto& [simplex, present] : circle_complex.simplices()) {
        (void)present;
        if (simplex.size() == 2) edge_basis.push_back(simplex);
    }
    std::vector<unsigned char> cycle_coordinates(edge_basis.size(), 0);
    for (std::size_t i = 0; i < edge_basis.size(); ++i) {
        const auto found = cycle.find(edge_basis[i]);
        if (found != cycle.end()) cycle_coordinates[i] =
            static_cast<unsigned char>(found->second & 1);
    }
    for (const auto& row : edge_boundary) {
        unsigned char value = 0;
        for (std::size_t column = 0; column < row.size(); ++column) {
            value ^= static_cast<unsigned char>((row[column] & cycle_coordinates[column]) & 1U);
        }
        assert(value == 0);
    }

    const auto disk_representatives =
        compute_f2_homology_representatives(FiniteSimplicialComplex(
            "filled-triangle-representatives", {{"A", "B", "C"}}));
    assert(disk_representatives[0].representatives.size() == 1);
    assert(disk_representatives[1].representatives.empty());
    assert(disk_representatives[2].representatives.empty());

    // Rank calculation handles row swaps, skipped pivot columns, and the
    // zero matrix over F_2.
    assert(rank_mod2({{0, 1}, {1, 1}}) == 2);
    assert(rank_mod2({{0, 1, 1}, {0, 0, 0}}) == 1);
    assert(rank_mod2({{0, 0}, {0, 0}}) == 0);

    std::cout << "simplicial boundary smoke: PASS\n";
    return 0;
}
