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

std::string cace_gate_id(
    std::string_view capability_id) {
    return
        "cace::" +
        std::string(capability_id);
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

    const bool expected_qualification_evidence =
        e.passed &&
        e.qualification_capability;
    if (e.qualification_evidence !=
        expected_qualification_evidence) {
        throw std::invalid_argument(
            "CACE qualification evidence semantics drift");
    }
}

VerificationGateRecord record_cace_verification_requirement(
    GenerationLineageStore& store,
    std::string_view generation_id,
    std::string_view capability_id,
    std::string_view request_evidence_hash) {
    if (generation_id.empty()) {
        throw std::invalid_argument(
            "generation_id must be non-empty");
    }

    const std::string capability(capability_id);
    const std::string request_hash(request_evidence_hash);

    if (!safe_identifier(capability)) {
        throw std::invalid_argument(
            "CACE capability_id must be a safe identifier");
    }
    if (!is_lower_hex(request_hash, 64U)) {
        throw std::invalid_argument(
            "CACE request evidence hash must be lowercase SHA-256");
    }

    (void)store.generation(generation_id);

    return store.record_verification_gate(
        VerificationGateRecord{
            .generation_id =
                std::string(generation_id),
            .gate_id =
                cace_gate_id(capability),
            .evaluator =
                "cace_tool_planner",
            .evidence_hash =
                request_hash,
            .passed = false,
            .required_for_promotion = true,
        });
}

CaceEvidenceReceipt record_cace_evaluation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    const CaceEvaluationEvidence& evidence) {
    if (generation_id.empty()) {
        throw std::invalid_argument(
            "generation_id must be non-empty");
    }

    validate_cace_evaluation_evidence(evidence);

    (void)store.generation(generation_id);

    const bool verified =
        evidence.passed &&
        evidence.qualification_capability;

    auto evaluation =
        store.record_evaluation(
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

    std::optional<VerificationGateRecord> gate;
    if (evidence.qualification_capability) {
        gate =
            store.record_verification_gate(
                VerificationGateRecord{
                    .generation_id =
                        std::string(generation_id),
                    .gate_id =
                        cace_gate_id(
                            evidence.capability_id),
                    .evaluator =
                        "cace_tool_broker:" +
                        evidence.capability_id,
                    .evidence_hash =
                        evidence.evaluation_evidence_hash,
                    .passed =
                        evidence.passed,
                    .required_for_promotion = true,
                });
    }

    return CaceEvidenceReceipt{
        .evaluation = std::move(evaluation),
        .verification_gate = std::move(gate),
    };
}

} // namespace expert_robot::growth
