#include "expert_robot/model_formalization_proposer.hpp"

#include "expert_robot/json_util.hpp"

#include <cctype>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot {
namespace {

const std::set<std::string> kAllowedKeys = {
    "name",
    "namespace",
    "binders",
    "proposition",
    "imports",
    "domain",
    "rationale",
};

void reject_unknown_top_level_keys(
    const std::string& json) {
    int depth = 0;
    bool in_string = false;
    bool escaped = false;

    for (std::size_t i = 0; i < json.size(); ++i) {
        const char ch = json[i];

        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }

        if (ch == '"') {
            if (depth == 1) {
                const std::size_t start = i + 1U;
                bool key_escaped = false;
                std::size_t end = start;
                for (; end < json.size(); ++end) {
                    const char k = json[end];
                    if (key_escaped) {
                        key_escaped = false;
                    } else if (k == '\\') {
                        key_escaped = true;
                    } else if (k == '"') {
                        break;
                    }
                }

                if (end >= json.size()) {
                    throw std::invalid_argument(
                        "unterminated JSON key");
                }

                std::size_t pos = end + 1U;
                while (pos < json.size() &&
                       std::isspace(
                           static_cast<unsigned char>(
                               json[pos]))) {
                    ++pos;
                }

                if (pos < json.size() &&
                    json[pos] == ':') {
                    const std::string key =
                        json.substr(
                            start,
                            end - start);
                    if (!kAllowedKeys.contains(key)) {
                        throw std::invalid_argument(
                            "unknown formalization proposal field: " +
                            key);
                    }
                }

                i = end;
                continue;
            }

            in_string = true;
            continue;
        }

        if (ch == '{' || ch == '[') {
            ++depth;
        } else if (ch == '}' || ch == ']') {
            --depth;
        }
    }
}

} // namespace

ModelFormalizationResult
parse_formalization_proposal_json(
    std::string_view raw) {
    const std::string json(raw);
    reject_unknown_top_level_keys(json);

    FormalizationProposal proposal{
        .name =
            json_util::string_field(
                json,
                "name"),
        .name_space =
            json_util::string_field(
                json,
                "namespace",
                "MathAI.Generated"),
        .binders = {},
        .proposition =
            json_util::string_field(
                json,
                "proposition"),
        .imports =
            json_util::string_array_field(
                json,
                "imports"),
        .domain =
            json_util::string_field(
                json,
                "domain",
                "unknown"),
        .rationale =
            json_util::string_field(
                json,
                "rationale"),
    };

    for (const auto& binder_json :
         json_util::object_array(
             json,
             "binders")) {
        proposal.binders.push_back(
            Binder{
                .name =
                    json_util::string_field(
                        binder_json,
                        "name"),
                .type =
                    json_util::string_field(
                        binder_json,
                        "type"),
            });
    }

    if (proposal.imports.empty()) {
        proposal.imports = {"MathAI"};
    }

    validate_formalization_proposal(
        proposal);

    return ModelFormalizationResult{
        .proposal = std::move(proposal),
        .raw_output = json,
    };
}

ModelFormalizationProposer::ModelFormalizationProposer(
    ITextGenerationBackend& backend)
    : backend_(backend) {}

ModelFormalizationResult
ModelFormalizationProposer::propose(
    const InformalFormalizationRequest& request) {
    if (request.name_hint.empty() ||
        request.informal_claim.empty()) {
        throw std::invalid_argument(
            "formalization request requires name_hint and informal_claim");
    }

    std::ostringstream prompt;
    prompt
        << "Convert the informal mathematical claim into ONE Lean theorem "
        << "statement proposal.\n"
        << "Return a statement only: never provide a proof, tactic script, "
        << "sorry, admit, axiom, unsafe declaration, command, or set_option.\n"
        << "Preserve mathematical meaning; do not strengthen the claim unless "
        << "the rationale explicitly identifies the change.\n\n"
        << "Name hint: " << request.name_hint << "\n"
        << "Namespace: " << request.name_space << "\n"
        << "Domain: " << request.domain << "\n"
        << "Informal claim:\n"
        << request.informal_claim
        << "\n\nContext:\n";

    for (const auto& item :
         request.context) {
        prompt << "- " << item << "\n";
    }

    prompt
        << "\nPreferred imports:\n";
    for (const auto& module :
         request.imports) {
        prompt << "- " << module << "\n";
    }

    prompt
        << "\nReturn JSON only with exactly these fields:\n"
        << "{\n"
        << "  \"name\": \"LeanSimpleName\",\n"
        << "  \"namespace\": \"" << request.name_space << "\",\n"
        << "  \"binders\": [{\"name\": \"x\", \"type\": \"LeanType\"}],\n"
        << "  \"proposition\": \"single Lean proposition expression\",\n"
        << "  \"imports\": [\"MathAI\"],\n"
        << "  \"domain\": \"" << request.domain << "\",\n"
        << "  \"rationale\": \"short mapping from informal claim to statement\"\n"
        << "}";

    const auto generated =
        backend_.generate(
            TextGenerationRequest{
                .system_prompt =
                    "You translate mathematical claims into candidate Lean "
                    "theorem statements only. You never generate proofs or "
                    "change verification authority.",
                .user_prompt = prompt.str(),
            });

    if (!generated.ok) {
        throw std::runtime_error(
            "model formalization proposal failed");
    }

    return parse_formalization_proposal_json(
        generated.output);
}

} // namespace expert_robot
