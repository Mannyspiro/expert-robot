#include "expert_robot/growth/cace_evidence.hpp"

#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <string>

namespace expert_robot::growth {
namespace {

bool is_lower_hex(
    const std::string& value,
    std::size_t size) {
    if (value.size() != size) return false;
    return std::all_of(
        value.begin(),
        value.end(),
        [](unsigned char ch) {
            return
                (ch >= '0' && ch <= '9') ||
                (ch >= 'a' && ch <= 'f');
        });
}

bool safe_identifier(
    const std::string& value) {
    if (value.empty() || value.size() > 128U) {
        return false;
    }

    const auto first =
        static_cast<unsigned char>(
            value.front());
    if (!std::isalnum(first)) {
        return false;
    }

    return std::all_of(
        value.begin(),
        value.end(),
        [](unsigned char ch) {
            return
                std::isalnum(ch) ||
                ch == '.' ||
                ch == '_' ||
                ch == ':' ||
                ch == '-';
        });
}

} // namespace

void validate_cace_evaluation_evidence(
    const CaceEvaluationEvidence& e) {
    if (!safe_identifier(e.request_id)) {
        throw std::invalid_argument(
            "CACE request_id must be a safe identifier");
    }
    if (!safe_identifier(e.capability_id)) {
        throw std::invalid_argument(
            "CACE capability_id must be a safe identifier");
    }

    if (!is_lower_hex(e.source_commit, 40U)) {
        throw std::invalid_argument(
            "CACE source_commit must be lowercase git SHA");
    }
    if (!is_lower_hex(e.cace_commit, 40U)) {
        throw std::invalid_argument(
            "CACE cace_commit must be lowercase git SHA");
    }

    for (const auto* item : {
             &e.evidence_sha256,
             &e.result_sha256,
             &e.evaluation_evidence_hash}) {
        if (!is_lower_hex(*item, 64U)) {
            throw std::invalid_argument(
                "CACE evidence hashes must be lowercase SHA-256");
        }
    }

    if (e.authority != "qualification-only") {
        throw std::invalid_argument(
            "CACE evidence authority must be qualification-only");
    }
    if (e.promotion_authority) {
        throw std::invalid_argument(
            "CACE evidence may not carry promotion authority");
    }
    if (e.monetary_cost != "free") {
        throw std::invalid_argument(
            "CACE evidence must come from a free lane");
    }
    if (e.wall_seconds < 0 || e.lean_checks < 0) {
        throw std::invalid_argument(
            "CACE compute counters must be nonnegative");
    }
    if (e.qualification_evidence && !e.passed) {
        throw std::invalid_argument(
            "failed CACE result cannot be qualification evidence");
    }
}

EvaluationRecord record_cace_evaluation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    const CaceEvaluationEvidence& evidence) {
    if (generation_id.empty()) {
        throw std::invalid_argument(
            "generation_id must be non-empty");
    }

    validate_cace_evaluation_evidence(evidence);

    // Confirm the referenced generation exists before recording evidence.
    (void)store.generation(generation_id);

    const bool verified =
        evidence.passed &&
        evidence.qualification_evidence;

    return store.record_evaluation(
        EvaluationRecord{
            .generation_id =
                std::string(generation_id),
            .evaluator =
                "cace_tool_broker:" +
                evidence.capability_id,
            .evidence_hash =
                evidence.evaluation_evidence_hash,
            .recommend_keep = false,
            .verification_ok = verified,
            .efficiency_ok = false,
            .diversity_ok = false,
            .verified_rate_delta = 0.0,
            .cost_per_verified_ratio = 0.0
        });
}

} // namespace expert_robot::growth
