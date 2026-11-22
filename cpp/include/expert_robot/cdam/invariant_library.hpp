#pragma once
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>
namespace expert_robot::cdam {
struct InvariantDefinition {
    std::string invariant_id, name, mathematical_statement;
    std::vector<std::string> applicable_domains, assumptions, known_limitations;
    std::string evidence_class{"reference"};
};
class InvariantLibrary {
public:
    explicit InvariantLibrary(std::vector<InvariantDefinition> definitions)
        : definitions_(std::move(definitions)) {
        std::unordered_set<std::string> ids;
        for (const auto& d : definitions_) {
            if (d.invariant_id.empty() || d.name.empty() || d.mathematical_statement.empty())
                throw std::invalid_argument("invariant identity, name and statement are required");
            if (!ids.insert(d.invariant_id).second)
                throw std::invalid_argument("duplicate invariant id: " + d.invariant_id);
        }
    }
    [[nodiscard]] static InvariantLibrary core() {
        return InvariantLibrary({
            {"invariant.conservation.mass", "Mass conservation",
             "Accumulation = inflow - outflow + production - consumption",
             {"fluid_dynamics","chemical_kinetics","ecology"},
             {"A control volume and flux convention are specified"},
             {"Source and sink terms must be modeled explicitly"}, "reference"},
            {"invariant.conservation.charge", "Charge conservation",
             "Net charge is conserved in a closed system", {"electrical_networks","electromagnetism"},
             {"The system boundary and charge flux are specified"},
             {"Open systems require explicit current terms"}, "reference"},
            {"invariant.network.node_balance", "Network node balance",
             "Signed sum of incident flows equals node accumulation",
             {"electrical_networks","fluid_networks","transport_networks"},
             {"Consistent orientation and sign convention"},
             {"Storage elements add dynamic accumulation terms"}, "reference"},
            {"invariant.energy.balance", "Energy balance",
             "Change in stored energy equals net transfer plus sources",
             {"thermodynamics","mechanics","electrical_networks"},
             {"System boundary and heat/work conventions are explicit"},
             {"Dissipation and external work must be included"}, "reference"},
            {"invariant.symmetry.translation", "Translation symmetry",
             "The governing relation is invariant under a declared translation group",
             {"geometry","physics","dynamical_systems"},
             {"The transformation group and action are specified"},
             {"Boundary conditions can break the symmetry"}, "reference"},
            {"invariant.dynamics.linear_state_space", "Linear state-space form",
             "x_dot = A x + B u over declared state and input spaces",
             {"control_theory","electrical_networks","mechanics"},
             {"The model is linear over the stated operating regime"},
             {"Nonlinear regimes require a different representation"}, "reference"},
            {"invariant.diffusion.parabolic", "Diffusion structure",
             "A parabolic evolution equation with a declared diffusion operator",
             {"heat_transfer","mass_transport","population_dynamics"},
             {"Regularity, domain and boundary conditions are stated"},
             {"Anisotropic and nonlinear diffusion need extended operators"}, "reference"},
            {"invariant.oscillation.second_order", "Second-order oscillatory dynamics",
             "A second-order state equation with inertia, damping and restoring terms",
             {"mechanics","electrical_networks","acoustics"},
             {"Constitutive terms and sign convention are specified"},
             {"Nonlinear and time-varying systems need separate qualification"}, "reference"}
        });
    }
    [[nodiscard]] const std::vector<InvariantDefinition>& all() const noexcept { return definitions_; }
private:
    std::vector<InvariantDefinition> definitions_;
};
} // namespace expert_robot::cdam
