#include "expert_robot/growth/ablation_evidence.hpp"

#include "expert_robot/sha256.hpp"

#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace expert_robot::growth {
namespace {

void append_summary(
    std::ostringstream& out,
    std::string_view label,
    const eval::VariantSummary& summary) {
    out
        << label << ".variant=" << summary.variant << "\n"
        << label << ".cases=" << summary.cases << "\n"
        << label << ".verified=" << summary.verified << "\n"
        << label << ".dead_end_escapes="
        << summary.dead_end_escapes << "\n"
        << label << ".total_wall_time_ms="
        << summary.total_wall_time_ms << "\n"
        << label << ".total_model_calls="
        << summary.total_model_calls << "\n"
        << label << ".total_proof_attempts="
        << summary.total_proof_attempts << "\n"
        << label << ".total_lemmas_generated="
        << summary.total_lemmas_generated << "\n"
        << label << ".total_ideas_generated="
        << summary.total_ideas_generated << "\n"
        << label << ".total_duplicate_candidates="
        << summary.total_duplicate_candidates << "\n"
        << label << ".total_resource_cost="
        << std::setprecision(17)
        << summary.total_resource_cost << "\n";
}

} // namespace

std::string ablation_evidence_hash(
    const eval::AblationResult& result) {
    std::ostringstream canonical;
    canonical << std::boolalpha;

    append_summary(
        canonical,
        "baseline",
        result.baseline);
    append_summary(
        canonical,
        "candidate",
        result.candidate);

    canonical
        << "verified_rate_delta="
        << std::setprecision(17)
        << result.verified_rate_delta << "\n"
        << "cost_per_verified_ratio="
        << result.cost_per_verified_ratio << "\n"
        << "duplicate_rate_delta="
        << result.duplicate_rate_delta << "\n"
        << "enough_cases="
        << result.enough_cases << "\n"
        << "verification_ok="
        << result.verification_ok << "\n"
        << "efficiency_ok="
        << result.efficiency_ok << "\n"
        << "diversity_ok="
        << result.diversity_ok << "\n"
        << "recommend_keep="
        << result.recommend_keep;

    return sha256_hex(
        canonical.str());
}

EvaluationRecord record_ablation_evidence(
    GenerationLineageStore& store,
    std::string_view generation_id,
    std::string_view evaluator,
    const eval::AblationResult& result) {
    if (generation_id.empty()) {
        throw std::invalid_argument(
            "generation_id must be non-empty");
    }
    if (evaluator.empty()) {
        throw std::invalid_argument(
            "evaluator must be non-empty");
    }

    const bool keep =
        result.enough_cases &&
        result.recommend_keep;

    return store.record_evaluation(
        EvaluationRecord{
            .generation_id =
                std::string(generation_id),
            .evaluator =
                std::string(evaluator),
            .evidence_hash =
                ablation_evidence_hash(result),
            .recommend_keep = keep,
            .verification_ok =
                result.enough_cases &&
                result.verification_ok,
            .efficiency_ok =
                result.enough_cases &&
                result.efficiency_ok,
            .diversity_ok =
                result.enough_cases &&
                result.diversity_ok,
            .verified_rate_delta =
                result.verified_rate_delta,
            .cost_per_verified_ratio =
                result.cost_per_verified_ratio,
        });
}

} // namespace expert_robot::growth
