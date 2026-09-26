#include "expert_robot/growth/cace_evidence.hpp"

#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::growth {
namespace {

void validate_text_identifier(
    const std::string& value,
    const char* label) {
    if (value.empty() || value.size() > 256U) {
        throw std::invalid_argument(
            std::string(label) +
            " must be non-empty and at most 256 characters");
    }
    for (const unsigned char ch : value) {
        if (ch < 0x20U || ch == 0x7fU) {
            throw std::invalid_argument(
                std::string(label) +
                " must not contain control characters");
        }
    }
}

void validate_sha256(
    const std::string& value,
    const char* label) {
    if (value.size() != 64U) {
        throw std::invalid_argument(
            std::string(label) +
            " must be a 64-character lowercase SHA-256");
    }
    for (const unsigned char ch : value) {
        const bool digit = ch >= '0' && ch <= '9';
        const bool lower = ch >= 'a' && ch <= 'f';
        if (!digit && !lower) {
            throw std::invalid_argument(
                std::string(label) +
                " must be a 64-character lowercase SHA-256");
        }
    }
}

std::string cace_gate_id(
    const std::string& capability_id) {
    return "cace::" + capability_id;
}

} // namespace

CaceEvidenceReceipt record_cace_evidence(
    GenerationLineageStore& store,
    CaceValidatedEvidence evidence) {
    validate_text_identifier(
        evidence.generation_id,
        "CACE evidence generation_id");
    validate_text_identifier(
        evidence.capability_id,
        "CACE evidence capability_id");
    validate_sha256(
        evidence.evaluation_evidence_hash,
        "CACE evaluation_evidence_hash");

    // Fail before recording anything if the target generation is unknown.
    (void)store.generation(
        evidence.generation_id);

    const std::string evaluator =
        cace_gate_id(
            evidence.capability_id);

    auto evaluation =
        store.record_evaluation(
            EvaluationRecord{
                .generation_id =
                    evidence.generation_id,
                .evaluator =
                    evaluator,
                .evidence_hash =
                    evidence.evaluation_evidence_hash,
                .recommend_keep =
                    evidence.passed,
                .verification_ok =
                    evidence.passed &&
                    evidence.qualification_capability,
                .efficiency_ok = false,
                .diversity_ok = false,
                .verified_rate_delta = 0.0,
                .cost_per_verified_ratio = 0.0,
            });

    std::optional<VerificationGateRecord> gate;
    if (evidence.qualification_capability) {
        gate =
            store.record_verification_gate(
                VerificationGateRecord{
                    .generation_id =
                        evidence.generation_id,
                    .gate_id =
                        evaluator,
                    .evaluator =
                        evaluator,
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
