#include "expert_robot/skills/model_skill_proposer.hpp"

#include "expert_robot/json_util.hpp"

#include <algorithm>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>

namespace expert_robot::skills {
namespace {

const std::set<std::string> kAllowedKeys = {
    "decision",
    "skill_id",
    "title",
    "lens",
    "role",
    "procedure",
};

const std::regex kObjectKey(
    R"REGEX("([^"]+)"s*:)REGEX");

const std::regex kForbiddenProcedure(
    R"REGEX((sorry|admit|axiom|unsafe|set_option|bypass|disable[ _-]?verification|credential|password|secret|network access|shell command|sudo|root access))REGEX",
    std::regex_constants::icase);

imagination::ImaginationLens parse_lens(
    const std::string& value) {
    using L = imagination::ImaginationLens;
    for (std::size_t i = 0;
         i < static_cast<std::size_t>(L::Count);
         ++i) {
        const auto lens = static_cast<L>(i);
        if (imagination::lens_name(lens) == value) {
            return lens;
        }
    }
    throw std::invalid_argument(
        "unsupported proposed skill lens: " + value);
}

swarm::AgentRole parse_role(
    const std::string& value) {
    using R = swarm::AgentRole;
    for (const auto role : {
             R::Mathematician,
             R::Skeptic,
             R::LemmaProposer,
             R::Analogist,
             R::GeometrySpecialist,
             R::Coder,
             R::Synthesizer}) {
        if (swarm::role_name(role) == value) {
            return role;
        }
    }
    throw std::invalid_argument(
        "unsupported proposed skill role: " + value);
}

void validate_procedure(
    const std::string& procedure) {
    if (procedure.empty()) {
        throw std::invalid_argument(
            "proposed skill procedure must be non-empty");
    }
    if (procedure.size() > 4096U) {
        throw std::invalid_argument(
            "proposed skill procedure exceeds size limit");
    }
    if (std::regex_search(
            procedure,
            kForbiddenProcedure)) {
        throw std::invalid_argument(
            "proposed skill procedure contains forbidden authority/proof bypass language");
    }
}

void reject_unknown_keys(
    const std::string& json) {
    for (auto it =
             std::sregex_iterator(
                 json.begin(),
                 json.end(),
                 kObjectKey);
         it != std::sregex_iterator();
         ++it) {
        const std::string key =
            (*it)[1].str();
        if (!kAllowedKeys.contains(key)) {
            throw std::invalid_argument(
                "unknown skill proposal field: " + key);
        }
    }
}

} // namespace

SkillProposalResult parse_skill_proposal_json(
    std::string_view raw) {
    const std::string json(raw);
    reject_unknown_keys(json);

    const std::string decision =
        json_util::string_field(
            json,
            "decision");

    if (decision == "NONE") {
        return SkillProposalResult{
            .proposed = false,
            .skill = std::nullopt,
            .raw_output = json,
        };
    }

    if (decision != "PROPOSE") {
        throw std::invalid_argument(
            "skill proposal decision must be PROPOSE or NONE");
    }

    MathSkill skill{
        .skill_id =
            json_util::string_field(
                json,
                "skill_id"),
        .title =
            json_util::string_field(
                json,
                "title"),
        .lens =
            parse_lens(
                json_util::string_field(
                    json,
                    "lens")),
        .preferred_role =
            parse_role(
                json_util::string_field(
                    json,
                    "role")),
        .procedure =
            json_util::string_field(
                json,
                "procedure"),
        .requires_lean_verification = true,
        .stage = SkillStage::Experimental,
    };

    if (!skill.skill_id.starts_with(
            "math.experimental.")) {
        throw std::invalid_argument(
            "model-proposed skill_id must use math.experimental.* namespace");
    }

    if (skill.title.empty()) {
        throw std::invalid_argument(
            "model-proposed skill title must be non-empty");
    }

    validate_procedure(skill.procedure);

    return SkillProposalResult{
        .proposed = true,
        .skill = std::move(skill),
        .raw_output = json,
    };
}

ModelSkillProposer::ModelSkillProposer(
    ITextGenerationBackend& backend)
    : backend_(backend) {}

SkillProposalResult ModelSkillProposer::propose(
    const SkillProposalContext& context) {
    if (context.recurring_pattern.empty() ||
        context.useful_method.empty()) {
        throw std::invalid_argument(
            "skill proposal context must contain pattern and useful method");
    }

    std::ostringstream prompt;
    prompt
        << "A recurring mathematical research pattern has been observed.\n"
        << "Decide whether it justifies a reusable procedural skill.\n"
        << "A skill is a bounded mathematical procedure, not a permission, "
        << "tool grant, proof, or authority change.\n"
        << "If no genuinely reusable procedure exists, return decision NONE.\n"
        << "If proposing, the skill_id MUST begin math.experimental. and the "
        << "procedure must preserve Lean verification.\n\n"
        << "Recurring pattern:\n"
        << context.recurring_pattern
        << "\n\nUseful method:\n"
        << context.useful_method
        << "\n\nExisting skill IDs:\n";

    for (const auto& id :
         context.existing_skill_ids) {
        prompt << "- " << id << "\n";
    }

    prompt
        << "\nReturn JSON only with exactly these fields:\n"
        << "{\n"
        << "  \"decision\": \"PROPOSE\" or \"NONE\",\n"
        << "  \"skill_id\": \"math.experimental...\",\n"
        << "  \"title\": \"...\",\n"
        << "  \"lens\": \"one of the registered imagination lens names\",\n"
        << "  \"role\": \"one of the registered swarm role names\",\n"
        << "  \"procedure\": \"bounded reusable mathematical procedure\"\n"
        << "}";

    const auto generated =
        backend_.generate(
            TextGenerationRequest{
                .system_prompt =
                    "You propose experimental mathematical procedures only. "
                    "Never propose permissions, credentials, network access, "
                    "proof bypasses, or changes to verification authority.",
                .user_prompt = prompt.str(),
            });

    if (!generated.ok) {
        throw std::runtime_error(
            "model skill proposal failed");
    }

    return parse_skill_proposal_json(
        generated.output);
}

} // namespace expert_robot::skills
