#include "expert_robot/eval/math_benchmark.hpp"

#include "expert_robot/json_util.hpp"

#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <stdexcept>
#include <tuple>
#include <utility>

namespace expert_robot::eval {
namespace {

BenchmarkSplit parse_split(
    std::string_view split) {
    if (split == "train") {
        return BenchmarkSplit::Train;
    }
    if (split == "holdout") {
        return BenchmarkSplit::Holdout;
    }
    throw std::invalid_argument(
        "benchmark split must be train or holdout");
}

void validate_case(
    const BenchmarkCase& c) {
    if (c.case_id.empty() ||
        c.family.empty() ||
        c.domain.empty() ||
        c.declaration_name.empty() ||
        c.name_space.empty() ||
        c.proposition.empty() ||
        c.imports.empty()) {
        throw std::invalid_argument(
            "benchmark case identifiers/domain/formal target must be non-empty");
    }
}

void validate_variant(
    const BenchmarkVariantProfile& v) {
    if (v.variant_id.empty()) {
        throw std::invalid_argument(
            "benchmark variant_id must be non-empty");
    }

    std::set<std::string> layers;
    for (const auto& layer :
         v.enabled_layers) {
        if (layer.empty()) {
            throw std::invalid_argument(
                "benchmark layer names must be non-empty");
        }
        if (!layers.insert(layer).second) {
            throw std::invalid_argument(
                "benchmark variant contains duplicate layer");
        }
    }
}

void validate_result(
    const BenchmarkCaseResult& r) {
    for (const auto value : {
             r.wall_time_ms,
             r.model_calls,
             r.proof_attempts,
             r.lemmas_generated,
             r.ideas_generated,
             r.duplicate_candidates}) {
        if (value < 0) {
            throw std::invalid_argument(
                "benchmark counters must be nonnegative");
        }
    }

    if (r.duplicate_candidates >
        r.ideas_generated) {
        throw std::invalid_argument(
            "benchmark duplicates cannot exceed generated ideas");
    }

    if (!std::isfinite(
            r.resource_cost) ||
        r.resource_cost < 0.0) {
        throw std::invalid_argument(
            "benchmark resource cost must be finite and nonnegative");
    }
}

std::string ledger_variant(
    std::string_view variant,
    BenchmarkSplit split) {
    return std::string(variant) +
           "::" +
           std::string(
               benchmark_split_name(
                   split));
}

struct SummaryKey {
    std::string variant;
    BenchmarkSplit split;
    std::string domain;

    bool operator<(
        const SummaryKey& other) const {
        return std::tie(
                   variant,
                   split,
                   domain) <
               std::tie(
                   other.variant,
                   other.split,
                   other.domain);
    }
};

void add_record(
    BenchmarkVariantSummary& summary,
    const MathEvalRecord& record) {
    ++summary.cases;
    if (record.verified) {
        ++summary.verified;
        if (record.model_calls == 0) {
            ++summary.zero_model_verified;
        }
    }
    if (record.dead_end_escaped) {
        ++summary.dead_end_escapes;
    }

    summary.total_wall_time_ms +=
        record.wall_time_ms;
    summary.total_model_calls +=
        record.model_calls;
    summary.total_proof_attempts +=
        record.proof_attempts;
    summary.total_lemmas_generated +=
        record.lemmas_generated;
    summary.total_ideas_generated +=
        record.ideas_generated;
    summary.total_duplicate_candidates +=
        record.duplicate_candidates;
    summary.total_resource_cost +=
        record.resource_cost;
}

} // namespace

std::string_view benchmark_split_name(
    BenchmarkSplit split) {
    switch (split) {
        case BenchmarkSplit::Train:
            return "train";
        case BenchmarkSplit::Holdout:
            return "holdout";
    }
    return "unknown";
}

bool BenchmarkVariantProfile::has_layer(
    std::string_view layer) const {
    return std::find(
               enabled_layers.begin(),
               enabled_layers.end(),
               layer) !=
           enabled_layers.end();
}

MathBenchmarkSuite::MathBenchmarkSuite(
    std::vector<BenchmarkCase> cases,
    std::vector<BenchmarkVariantProfile> variants)
    : cases_(std::move(cases)),
      variants_(std::move(variants)) {
    if (cases_.empty()) {
        throw std::invalid_argument(
            "benchmark suite requires at least one case");
    }
    if (variants_.empty()) {
        throw std::invalid_argument(
            "benchmark suite requires at least one variant");
    }

    std::set<std::string> case_ids;
    std::map<std::string, BenchmarkSplit>
        family_split;
    bool saw_train = false;
    bool saw_holdout = false;

    for (const auto& c : cases_) {
        validate_case(c);

        if (!case_ids.insert(
                c.case_id).second) {
            throw std::invalid_argument(
                "duplicate benchmark case_id: " +
                c.case_id);
        }

        const auto [it, inserted] =
            family_split.emplace(
                c.family,
                c.split);

        if (!inserted &&
            it->second != c.split) {
            throw std::invalid_argument(
                "benchmark family leaks across train/holdout: " +
                c.family);
        }

        saw_train =
            saw_train ||
            c.split == BenchmarkSplit::Train;
        saw_holdout =
            saw_holdout ||
            c.split == BenchmarkSplit::Holdout;
    }

    if (!saw_train || !saw_holdout) {
        throw std::invalid_argument(
            "benchmark suite requires both train and holdout cases");
    }

    std::set<std::string> variant_ids;
    for (const auto& variant :
         variants_) {
        validate_variant(variant);
        if (!variant_ids.insert(
                variant.variant_id).second) {
            throw std::invalid_argument(
                "duplicate benchmark variant_id: " +
                variant.variant_id);
        }
    }
}

MathBenchmarkSuite MathBenchmarkSuite::load_json(
    const std::filesystem::path& path) {
    const std::string json =
        json_util::read_file(
            path.string());

    if (json_util::int_field(
            json,
            "schema_version",
            -1) != 1) {
        throw std::invalid_argument(
            "unsupported math benchmark schema_version");
    }

    std::vector<BenchmarkCase> cases;
    for (const auto& object :
         json_util::object_array(
             json,
             "cases")) {
        std::vector<BenchmarkBinder> binders;
        for (const auto& binder :
             json_util::object_array(
                 object,
                 "binders")) {
            binders.push_back(
                BenchmarkBinder{
                    .name =
                        json_util::string_field(
                            binder,
                            "name"),
                    .type =
                        json_util::string_field(
                            binder,
                            "type"),
                });
        }

        cases.push_back(
            BenchmarkCase{
                .case_id =
                    json_util::string_field(
                        object,
                        "case_id"),
                .family =
                    json_util::string_field(
                        object,
                        "family"),
                .domain =
                    json_util::string_field(
                        object,
                        "domain"),
                .focus_theorem =
                    json_util::string_field(
                        object,
                        "focus_theorem"),
                .declaration_name =
                    json_util::string_field(
                        object,
                        "declaration_name"),
                .name_space =
                    json_util::string_field(
                        object,
                        "namespace",
                        "MathAI.Benchmark"),
                .binders =
                    std::move(binders),
                .proposition =
                    json_util::string_field(
                        object,
                        "proposition"),
                .imports =
                    json_util::string_array_field(
                        object,
                        "imports"),
                .split =
                    parse_split(
                        json_util::string_field(
                            object,
                            "split")),
                .tags =
                    json_util::string_array_field(
                        object,
                        "tags"),
            });
    }

    std::vector<BenchmarkVariantProfile>
        variants;
    for (const auto& object :
         json_util::object_array(
             json,
             "variants")) {
        variants.push_back(
            BenchmarkVariantProfile{
                .variant_id =
                    json_util::string_field(
                        object,
                        "variant_id"),
                .enabled_layers =
                    json_util::string_array_field(
                        object,
                        "enabled_layers"),
            });
    }

    return MathBenchmarkSuite(
        std::move(cases),
        std::move(variants));
}

const std::vector<BenchmarkCase>&
MathBenchmarkSuite::cases() const noexcept {
    return cases_;
}

const std::vector<BenchmarkVariantProfile>&
MathBenchmarkSuite::variants() const noexcept {
    return variants_;
}

std::vector<BenchmarkCase>
MathBenchmarkSuite::cases_for_split(
    BenchmarkSplit split) const {
    std::vector<BenchmarkCase> result;
    for (const auto& c : cases_) {
        if (c.split == split) {
            result.push_back(c);
        }
    }
    return result;
}

double BenchmarkVariantSummary::verified_rate() const noexcept {
    return cases > 0
        ? static_cast<double>(verified) /
              static_cast<double>(cases)
        : 0.0;
}

double BenchmarkVariantSummary::zero_model_verified_rate() const noexcept {
    return cases > 0
        ? static_cast<double>(
              zero_model_verified) /
              static_cast<double>(cases)
        : 0.0;
}

double BenchmarkVariantSummary::average_model_calls() const noexcept {
    return cases > 0
        ? static_cast<double>(
              total_model_calls) /
              static_cast<double>(cases)
        : 0.0;
}

double BenchmarkVariantSummary::average_proof_attempts() const noexcept {
    return cases > 0
        ? static_cast<double>(
              total_proof_attempts) /
              static_cast<double>(cases)
        : 0.0;
}

double BenchmarkVariantSummary::average_resource_cost() const noexcept {
    return cases > 0
        ? total_resource_cost /
              static_cast<double>(cases)
        : 0.0;
}

MathBenchmarkRunner::MathBenchmarkRunner(
    MathEvalLedger* ledger)
    : ledger_(ledger) {}

BenchmarkRun MathBenchmarkRunner::run(
    std::string run_id,
    const MathBenchmarkSuite& suite,
    IMathBenchmarkExecutor& executor) const {
    if (run_id.empty()) {
        throw std::invalid_argument(
            "benchmark run_id must be non-empty");
    }

    BenchmarkRun run;
    run.run_id = run_id;

    std::map<SummaryKey, BenchmarkVariantSummary>
        summaries;

    for (const auto& variant :
         suite.variants()) {
        for (const auto& benchmark_case :
             suite.cases()) {
            const auto outcome =
                executor.run(
                    variant,
                    benchmark_case);
            validate_result(outcome);

            MathEvalRecord record{
                .run_id = run_id,
                .variant =
                    ledger_variant(
                        variant.variant_id,
                        benchmark_case.split),
                .case_id =
                    benchmark_case.case_id,
                .domain =
                    benchmark_case.domain,
                .verified =
                    outcome.verified,
                .dead_end_escaped =
                    outcome.dead_end_escaped,
                .wall_time_ms =
                    outcome.wall_time_ms,
                .model_calls =
                    outcome.model_calls,
                .proof_attempts =
                    outcome.proof_attempts,
                .lemmas_generated =
                    outcome.lemmas_generated,
                .ideas_generated =
                    outcome.ideas_generated,
                .duplicate_candidates =
                    outcome.duplicate_candidates,
                .resource_cost =
                    outcome.resource_cost,
            };

            validate_eval_record(record);

            if (ledger_ != nullptr) {
                ledger_->record(record);
            }

            run.records.push_back(
                record);

            for (const std::string domain :
                 {std::string("all"),
                  benchmark_case.domain}) {
                SummaryKey key{
                    .variant =
                        variant.variant_id,
                    .split =
                        benchmark_case.split,
                    .domain =
                        domain,
                };

                auto [it, inserted] =
                    summaries.emplace(
                        key,
                        BenchmarkVariantSummary{
                            .run_id = run_id,
                            .variant_id =
                                variant.variant_id,
                            .split =
                                benchmark_case.split,
                            .domain =
                                domain,
                        });
                (void)inserted;
                add_record(
                    it->second,
                    record);
            }
        }
    }

    for (auto& [key, summary] :
         summaries) {
        (void)key;
        run.summaries.push_back(
            std::move(summary));
    }

    return run;
}

} // namespace expert_robot::eval
