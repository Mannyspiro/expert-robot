#include "expert_robot/eval/math_eval.hpp"

#include <sqlite3.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::eval {
namespace {

constexpr int kSchemaVersion = 1;

void check(int code, sqlite3* db, const char* context) {
    if (code != SQLITE_OK &&
        code != SQLITE_DONE &&
        code != SQLITE_ROW) {
        throw std::runtime_error(
            std::string(context) + ": " +
            (db ? sqlite3_errmsg(db) : "sqlite error"));
    }
}

void exec_sql(sqlite3* db, const char* sql) {
    char* error = nullptr;
    const int rc =
        sqlite3_exec(db, sql, nullptr, nullptr, &error);
    if (rc != SQLITE_OK) {
        const std::string message =
            error ? error : "sqlite exec failed";
        sqlite3_free(error);
        throw std::runtime_error(message);
    }
}

class Statement {
public:
    Statement(sqlite3* db, const char* sql)
        : db_(db) {
        check(
            sqlite3_prepare_v2(
                db_, sql, -1, &stmt_, nullptr),
            db_,
            "prepare math eval statement");
    }

    ~Statement() {
        if (stmt_) sqlite3_finalize(stmt_);
    }

    sqlite3_stmt* get() const noexcept {
        return stmt_;
    }

private:
    sqlite3* db_{nullptr};
    sqlite3_stmt* stmt_{nullptr};
};

void bind_text(
    sqlite3* db,
    sqlite3_stmt* stmt,
    int index,
    std::string_view value) {
    check(
        sqlite3_bind_text(
            stmt,
            index,
            value.data(),
            static_cast<int>(value.size()),
            SQLITE_TRANSIENT),
        db,
        "bind math eval text");
}

std::string text_column(sqlite3_stmt* stmt, int index) {
    const auto* raw =
        reinterpret_cast<const char*>(
            sqlite3_column_text(stmt, index));
    return raw ? std::string(raw) : std::string{};
}

MathEvalRecord row_to_record(sqlite3_stmt* stmt) {
    return MathEvalRecord{
        .run_id = text_column(stmt, 0),
        .variant = text_column(stmt, 1),
        .case_id = text_column(stmt, 2),
        .domain = text_column(stmt, 3),
        .verified = sqlite3_column_int(stmt, 4) != 0,
        .dead_end_escaped = sqlite3_column_int(stmt, 5) != 0,
        .wall_time_ms = sqlite3_column_int64(stmt, 6),
        .model_calls = sqlite3_column_int64(stmt, 7),
        .proof_attempts = sqlite3_column_int64(stmt, 8),
        .lemmas_generated = sqlite3_column_int64(stmt, 9),
        .ideas_generated = sqlite3_column_int64(stmt, 10),
        .duplicate_candidates = sqlite3_column_int64(stmt, 11),
        .resource_cost = sqlite3_column_double(stmt, 12),
    };
}

} // namespace

double VariantSummary::verified_rate() const noexcept {
    return cases > 0
        ? static_cast<double>(verified) /
              static_cast<double>(cases)
        : 0.0;
}

double VariantSummary::average_resource_cost() const noexcept {
    return cases > 0
        ? total_resource_cost /
              static_cast<double>(cases)
        : 0.0;
}

double VariantSummary::resource_cost_per_verified() const noexcept {
    return verified > 0
        ? total_resource_cost /
              static_cast<double>(verified)
        : std::numeric_limits<double>::infinity();
}

double VariantSummary::duplicate_rate() const noexcept {
    return total_ideas_generated > 0
        ? static_cast<double>(total_duplicate_candidates) /
              static_cast<double>(total_ideas_generated)
        : 0.0;
}

void validate_eval_record(const MathEvalRecord& r) {
    if (r.run_id.empty() ||
        r.variant.empty() ||
        r.case_id.empty() ||
        r.domain.empty()) {
        throw std::invalid_argument(
            "math eval identifiers/domain must be non-empty");
    }

    for (const auto value : {
             r.wall_time_ms,
             r.model_calls,
             r.proof_attempts,
             r.lemmas_generated,
             r.ideas_generated,
             r.duplicate_candidates}) {
        if (value < 0) {
            throw std::invalid_argument(
                "math eval counters must be nonnegative");
        }
    }

    if (!std::isfinite(r.resource_cost) ||
        r.resource_cost < 0.0) {
        throw std::invalid_argument(
            "math eval resource_cost must be finite and nonnegative");
    }

    if (r.duplicate_candidates > r.ideas_generated) {
        throw std::invalid_argument(
            "duplicate_candidates cannot exceed ideas_generated");
    }
}

void validate_ablation_policy(const AblationPolicy& p) {
    if (p.minimum_cases <= 0) {
        throw std::invalid_argument(
            "ablation minimum_cases must be positive");
    }

    for (const auto value : {
             p.maximum_verified_rate_regression,
             p.meaningful_verified_rate_gain,
             p.maximum_duplicate_rate_increase}) {
        if (!std::isfinite(value) ||
            value < 0.0 ||
            value > 1.0) {
            throw std::invalid_argument(
                "ablation rate thresholds must be in [0,1]");
        }
    }

    if (!std::isfinite(
            p.maximum_cost_multiplier_without_accuracy_gain) ||
        p.maximum_cost_multiplier_without_accuracy_gain < 1.0) {
        throw std::invalid_argument(
            "ablation cost multiplier must be >= 1");
    }
}

AblationResult compare_variants(
    const VariantSummary& baseline,
    const VariantSummary& candidate,
    const AblationPolicy& policy) {
    validate_ablation_policy(policy);

    AblationResult result;
    result.baseline = baseline;
    result.candidate = candidate;

    result.verified_rate_delta =
        candidate.verified_rate() -
        baseline.verified_rate();

    const double baseline_cost =
        baseline.resource_cost_per_verified();
    const double candidate_cost =
        candidate.resource_cost_per_verified();

    if (std::isfinite(baseline_cost) &&
        baseline_cost > 0.0) {
        result.cost_per_verified_ratio =
            candidate_cost / baseline_cost;
    } else if (std::isfinite(candidate_cost)) {
        result.cost_per_verified_ratio = 1.0;
    } else {
        result.cost_per_verified_ratio =
            std::numeric_limits<double>::infinity();
    }

    result.duplicate_rate_delta =
        candidate.duplicate_rate() -
        baseline.duplicate_rate();

    result.enough_cases =
        baseline.cases >= policy.minimum_cases &&
        candidate.cases >= policy.minimum_cases;

    result.verification_ok =
        result.verified_rate_delta >=
        -policy.maximum_verified_rate_regression;

    const bool meaningful_gain =
        result.verified_rate_delta >=
        policy.meaningful_verified_rate_gain;

    result.efficiency_ok =
        meaningful_gain ||
        result.cost_per_verified_ratio <=
            policy.maximum_cost_multiplier_without_accuracy_gain;

    result.diversity_ok =
        result.duplicate_rate_delta <=
        policy.maximum_duplicate_rate_increase;

    result.recommend_keep =
        result.enough_cases &&
        result.verification_ok &&
        result.efficiency_ok &&
        result.diversity_ok;

    return result;
}

MathEvalLedger::MathEvalLedger(
    std::filesystem::path path)
    : path_(std::move(path)) {
    if (!path_.parent_path().empty()) {
        std::filesystem::create_directories(
            path_.parent_path());
    }

    const int rc =
        sqlite3_open(
            path_.string().c_str(),
            &db_);
    if (rc != SQLITE_OK) {
        const std::string message =
            db_ ? sqlite3_errmsg(db_) : "sqlite open failed";
        if (db_) sqlite3_close(db_);
        db_ = nullptr;
        throw std::runtime_error(message);
    }

    initialize();
}

MathEvalLedger::~MathEvalLedger() {
    if (db_) sqlite3_close(db_);
}

void MathEvalLedger::initialize() {
    exec_sql(
        db_,
        R"SQL(
        CREATE TABLE IF NOT EXISTS math_eval_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS math_eval_records (
            run_id TEXT NOT NULL,
            variant TEXT NOT NULL,
            case_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            verified INTEGER NOT NULL CHECK(verified IN (0,1)),
            dead_end_escaped INTEGER NOT NULL CHECK(dead_end_escaped IN (0,1)),
            wall_time_ms INTEGER NOT NULL,
            model_calls INTEGER NOT NULL,
            proof_attempts INTEGER NOT NULL,
            lemmas_generated INTEGER NOT NULL,
            ideas_generated INTEGER NOT NULL,
            duplicate_candidates INTEGER NOT NULL,
            resource_cost REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(run_id, variant, case_id)
        );

        CREATE INDEX IF NOT EXISTS idx_math_eval_variant
            ON math_eval_records(variant);
        )SQL");

    Statement query(
        db_,
        "SELECT value FROM math_eval_metadata "
        "WHERE key='schema_version';");

    const int rc = sqlite3_step(query.get());
    check(rc, db_, "read math eval schema");

    if (rc == SQLITE_DONE) {
        Statement insert(
            db_,
            "INSERT INTO math_eval_metadata(key,value) "
            "VALUES('schema_version','1');");
        check(
            sqlite3_step(insert.get()),
            db_,
            "insert math eval schema");
    } else {
        const auto* raw =
            reinterpret_cast<const char*>(
                sqlite3_column_text(
                    query.get(),
                    0));
        if (!raw ||
            std::string(raw) !=
                std::to_string(kSchemaVersion)) {
            throw std::runtime_error(
                "unsupported math eval schema");
        }
    }
}

void MathEvalLedger::record(
    const MathEvalRecord& r) {
    validate_eval_record(r);

    Statement stmt(
        db_,
        R"SQL(
        INSERT INTO math_eval_records(
            run_id,variant,case_id,domain,
            verified,dead_end_escaped,
            wall_time_ms,model_calls,proof_attempts,
            lemmas_generated,ideas_generated,
            duplicate_candidates,resource_cost
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?);
        )SQL");

    bind_text(db_, stmt.get(), 1, r.run_id);
    bind_text(db_, stmt.get(), 2, r.variant);
    bind_text(db_, stmt.get(), 3, r.case_id);
    bind_text(db_, stmt.get(), 4, r.domain);

    check(sqlite3_bind_int(stmt.get(), 5, r.verified ? 1 : 0), db_, "bind verified");
    check(sqlite3_bind_int(stmt.get(), 6, r.dead_end_escaped ? 1 : 0), db_, "bind dead_end_escaped");
    check(sqlite3_bind_int64(stmt.get(), 7, r.wall_time_ms), db_, "bind wall_time");
    check(sqlite3_bind_int64(stmt.get(), 8, r.model_calls), db_, "bind model_calls");
    check(sqlite3_bind_int64(stmt.get(), 9, r.proof_attempts), db_, "bind proof_attempts");
    check(sqlite3_bind_int64(stmt.get(), 10, r.lemmas_generated), db_, "bind lemmas_generated");
    check(sqlite3_bind_int64(stmt.get(), 11, r.ideas_generated), db_, "bind ideas_generated");
    check(sqlite3_bind_int64(stmt.get(), 12, r.duplicate_candidates), db_, "bind duplicates");
    check(sqlite3_bind_double(stmt.get(), 13, r.resource_cost), db_, "bind resource_cost");

    check(
        sqlite3_step(stmt.get()),
        db_,
        "insert math eval record");
}

VariantSummary MathEvalLedger::summarize(
    std::string_view variant) const {
    if (variant.empty()) {
        throw std::invalid_argument(
            "math eval variant must be non-empty");
    }

    Statement stmt(
        db_,
        R"SQL(
        SELECT
            COUNT(*),
            COALESCE(SUM(verified),0),
            COALESCE(SUM(dead_end_escaped),0),
            COALESCE(SUM(wall_time_ms),0),
            COALESCE(SUM(model_calls),0),
            COALESCE(SUM(proof_attempts),0),
            COALESCE(SUM(lemmas_generated),0),
            COALESCE(SUM(ideas_generated),0),
            COALESCE(SUM(duplicate_candidates),0),
            COALESCE(SUM(resource_cost),0.0)
        FROM math_eval_records
        WHERE variant=?;
        )SQL");

    bind_text(db_, stmt.get(), 1, variant);

    const int rc = sqlite3_step(stmt.get());
    check(rc, db_, "summarize math eval variant");

    VariantSummary summary;
    summary.variant = std::string(variant);

    if (rc == SQLITE_ROW) {
        summary.cases = sqlite3_column_int64(stmt.get(), 0);
        summary.verified = sqlite3_column_int64(stmt.get(), 1);
        summary.dead_end_escapes = sqlite3_column_int64(stmt.get(), 2);
        summary.total_wall_time_ms = sqlite3_column_int64(stmt.get(), 3);
        summary.total_model_calls = sqlite3_column_int64(stmt.get(), 4);
        summary.total_proof_attempts = sqlite3_column_int64(stmt.get(), 5);
        summary.total_lemmas_generated = sqlite3_column_int64(stmt.get(), 6);
        summary.total_ideas_generated = sqlite3_column_int64(stmt.get(), 7);
        summary.total_duplicate_candidates = sqlite3_column_int64(stmt.get(), 8);
        summary.total_resource_cost = sqlite3_column_double(stmt.get(), 9);
    }

    return summary;
}

std::vector<MathEvalRecord>
MathEvalLedger::records(
    std::string_view variant) const {
    const bool filtered = !variant.empty();

    Statement stmt(
        db_,
        filtered
            ? "SELECT run_id,variant,case_id,domain,verified,"
              "dead_end_escaped,wall_time_ms,model_calls,proof_attempts,"
              "lemmas_generated,ideas_generated,duplicate_candidates,"
              "resource_cost FROM math_eval_records "
              "WHERE variant=? ORDER BY run_id,case_id;"
            : "SELECT run_id,variant,case_id,domain,verified,"
              "dead_end_escaped,wall_time_ms,model_calls,proof_attempts,"
              "lemmas_generated,ideas_generated,duplicate_candidates,"
              "resource_cost FROM math_eval_records "
              "ORDER BY variant,run_id,case_id;");

    if (filtered) {
        bind_text(db_, stmt.get(), 1, variant);
    }

    std::vector<MathEvalRecord> result;

    while (true) {
        const int rc = sqlite3_step(stmt.get());
        check(rc, db_, "read math eval records");
        if (rc == SQLITE_DONE) break;
        result.push_back(row_to_record(stmt.get()));
    }

    return result;
}

} // namespace expert_robot::eval
