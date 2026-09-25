#include "expert_robot/skills/skill_ledger.hpp"

#include <sqlite3.h>

#include <algorithm>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::skills {
namespace {

constexpr int kSchemaVersion = 1;

void check(
    int code,
    sqlite3* db,
    const char* context) {
    if (code != SQLITE_OK &&
        code != SQLITE_DONE &&
        code != SQLITE_ROW) {
        throw std::runtime_error(
            std::string(context) +
            ": " +
            (db ? sqlite3_errmsg(db) : "sqlite error"));
    }
}

void exec_sql(sqlite3* db, const char* sql) {
    char* error = nullptr;
    const int rc =
        sqlite3_exec(
            db,
            sql,
            nullptr,
            nullptr,
            &error);
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
                db_,
                sql,
                -1,
                &stmt_,
                nullptr),
            db_,
            "prepare skill ledger statement");
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
        "bind skill ledger text");
}

SkillStats row_to_stats(sqlite3_stmt* stmt) {
    const auto* raw =
        reinterpret_cast<const char*>(
            sqlite3_column_text(stmt, 0));
    return SkillStats{
        .skill_id = raw ? raw : "",
        .attempts = sqlite3_column_int64(stmt, 1),
        .skeptic_passes = sqlite3_column_int64(stmt, 2),
        .shortlisted = sqlite3_column_int64(stmt, 3),
        .downstream_verified = sqlite3_column_int64(stmt, 4),
        .downstream_failed = sqlite3_column_int64(stmt, 5),
    };
}

} // namespace

double SkillStats::verified_rate() const noexcept {
    return attempts > 0
        ? static_cast<double>(downstream_verified) /
              static_cast<double>(attempts)
        : 0.0;
}

double SkillStats::shortlist_rate() const noexcept {
    return attempts > 0
        ? static_cast<double>(shortlisted) /
              static_cast<double>(attempts)
        : 0.0;
}

SkillStage recommended_stage(
    const SkillStats& s,
    const SkillQualificationPolicy& p) {
    if (p.minimum_attempts < 1 ||
        p.minimum_verified < 0 ||
        p.minimum_verified_rate < 0.0 ||
        p.minimum_verified_rate > 1.0 ||
        p.minimum_shortlist_rate < 0.0 ||
        p.minimum_shortlist_rate > 1.0) {
        throw std::invalid_argument(
            "invalid skill qualification policy");
    }

    if (s.attempts < p.minimum_attempts ||
        s.downstream_verified < p.minimum_verified) {
        return SkillStage::Experimental;
    }

    if (s.verified_rate() >= p.minimum_verified_rate &&
        s.shortlist_rate() >= p.minimum_shortlist_rate) {
        return SkillStage::Qualified;
    }

    const long long resolved =
        s.downstream_verified +
        s.downstream_failed;

    if (resolved >= p.minimum_attempts &&
        s.downstream_verified == 0) {
        return SkillStage::Deprecated;
    }

    return SkillStage::Experimental;
}

SkillLedger::SkillLedger(
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

SkillLedger::~SkillLedger() {
    if (db_) sqlite3_close(db_);
}

void SkillLedger::initialize() {
    exec_sql(
        db_,
        R"SQL(
        CREATE TABLE IF NOT EXISTS skill_ledger_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS skill_outcomes (
            skill_id TEXT PRIMARY KEY,
            attempts INTEGER NOT NULL DEFAULT 0,
            skeptic_passes INTEGER NOT NULL DEFAULT 0,
            shortlisted INTEGER NOT NULL DEFAULT 0,
            downstream_verified INTEGER NOT NULL DEFAULT 0,
            downstream_failed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        )SQL");

    Statement query(
        db_,
        "SELECT value FROM skill_ledger_metadata "
        "WHERE key='schema_version';");

    const int rc = sqlite3_step(query.get());
    check(rc, db_, "read skill ledger schema");

    if (rc == SQLITE_DONE) {
        Statement insert(
            db_,
            "INSERT INTO skill_ledger_metadata(key,value) "
            "VALUES('schema_version','1');");
        check(
            sqlite3_step(insert.get()),
            db_,
            "insert skill ledger schema");
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
                "unsupported skill ledger schema");
        }
    }
}

void SkillLedger::record(
    std::string_view skill_id,
    const SkillOutcome& outcome) {
    if (skill_id.empty()) {
        throw std::invalid_argument(
            "skill ledger skill_id must be non-empty");
    }

    Statement stmt(
        db_,
        R"SQL(
        INSERT INTO skill_outcomes(
            skill_id,
            attempts,
            skeptic_passes,
            shortlisted,
            downstream_verified,
            downstream_failed,
            updated_at
        ) VALUES (?,1,?,?,?,?,CURRENT_TIMESTAMP)
        ON CONFLICT(skill_id) DO UPDATE SET
            attempts=attempts+1,
            skeptic_passes=skeptic_passes+excluded.skeptic_passes,
            shortlisted=shortlisted+excluded.shortlisted,
            downstream_verified=downstream_verified+excluded.downstream_verified,
            downstream_failed=downstream_failed+excluded.downstream_failed,
            updated_at=CURRENT_TIMESTAMP;
        )SQL");

    bind_text(
        db_,
        stmt.get(),
        1,
        skill_id);

    check(
        sqlite3_bind_int(
            stmt.get(),
            2,
            outcome.skeptic_passed ? 1 : 0),
        db_,
        "bind skeptic_passed");

    check(
        sqlite3_bind_int(
            stmt.get(),
            3,
            outcome.shortlisted ? 1 : 0),
        db_,
        "bind shortlisted");

    check(
        sqlite3_bind_int(
            stmt.get(),
            4,
            outcome.downstream_verified ? 1 : 0),
        db_,
        "bind downstream_verified");

    check(
        sqlite3_bind_int(
            stmt.get(),
            5,
            outcome.downstream_failed ? 1 : 0),
        db_,
        "bind downstream_failed");

    check(
        sqlite3_step(stmt.get()),
        db_,
        "record skill outcome");
}

SkillStats SkillLedger::stats(
    std::string_view skill_id) const {
    Statement stmt(
        db_,
        "SELECT skill_id,attempts,skeptic_passes,shortlisted,"
        "downstream_verified,downstream_failed "
        "FROM skill_outcomes WHERE skill_id=?;");

    bind_text(
        db_,
        stmt.get(),
        1,
        skill_id);

    const int rc = sqlite3_step(stmt.get());
    check(rc, db_, "read skill stats");

    if (rc == SQLITE_DONE) {
        return SkillStats{
            .skill_id = std::string(skill_id),
        };
    }

    return row_to_stats(stmt.get());
}

std::vector<SkillStats>
SkillLedger::all_stats() const {
    Statement stmt(
        db_,
        "SELECT skill_id,attempts,skeptic_passes,shortlisted,"
        "downstream_verified,downstream_failed "
        "FROM skill_outcomes ORDER BY skill_id;");

    std::vector<SkillStats> result;

    while (true) {
        const int rc =
            sqlite3_step(stmt.get());
        check(rc, db_, "read all skill stats");
        if (rc == SQLITE_DONE) break;
        result.push_back(
            row_to_stats(stmt.get()));
    }

    return result;
}

} // namespace expert_robot::skills
