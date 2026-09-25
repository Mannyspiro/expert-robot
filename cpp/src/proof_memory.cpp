#include "expert_robot/proof_memory.hpp"
#include "expert_robot/json_util.hpp"
#include "expert_robot/sha256.hpp"

#include <algorithm>
#include <map>
#include <sqlite3.h>
#include <sstream>
#include <stdexcept>
#include <tuple>

namespace expert_robot {
namespace {

constexpr int kSchemaVersion = 1;

void check_sql(int code, sqlite3* db, const char* context) {
    if (code != SQLITE_OK && code != SQLITE_DONE && code != SQLITE_ROW) {
        throw std::runtime_error(
            std::string(context) + ": " + (db ? sqlite3_errmsg(db) : "sqlite error"));
    }
}

void exec_sql(sqlite3* db, const char* sql) {
    char* error = nullptr;
    const int rc = sqlite3_exec(db, sql, nullptr, nullptr, &error);
    if (rc != SQLITE_OK) {
        const std::string message = error ? error : "sqlite exec failed";
        sqlite3_free(error);
        throw std::runtime_error(message);
    }
}

std::string canonical_string_array(const std::vector<std::string>& values) {
    std::ostringstream out;
    out << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ",";
        out << "\"" << json_util::escape_ascii(values[i]) << "\"";
    }
    out << "]";
    return out.str();
}

class Statement {
public:
    Statement(sqlite3* db, const char* sql) : db_(db) {
        check_sql(sqlite3_prepare_v2(db_, sql, -1, &stmt_, nullptr), db_, "prepare");
    }
    ~Statement() {
        if (stmt_) sqlite3_finalize(stmt_);
    }
    sqlite3_stmt* get() const noexcept { return stmt_; }
private:
    sqlite3* db_{};
    sqlite3_stmt* stmt_{};
};

void bind_text(sqlite3* db, sqlite3_stmt* stmt, int index, const std::string& value) {
    check_sql(
        sqlite3_bind_text(stmt, index, value.c_str(), static_cast<int>(value.size()), SQLITE_TRANSIENT),
        db,
        "bind text");
}

long long scalar_int64(sqlite3* db, const char* sql) {
    Statement stmt(db, sql);
    const int rc = sqlite3_step(stmt.get());
    check_sql(rc, db, "step scalar");
    if (rc != SQLITE_ROW) return 0;
    return sqlite3_column_int64(stmt.get(), 0);
}

} // namespace

std::string goal_fingerprint(const SearchProblem& problem) {
    std::ostringstream canonical;
    canonical
        << "{\"context_declarations\":" << canonical_string_array(problem.context_declarations)
        << ",\"imports\":" << canonical_string_array(problem.imports)
        << ",\"statement\":\"" << json_util::escape_ascii(problem.statement) << "\"}";
    return sha256_hex(canonical.str());
}

ProofMemory::ProofMemory(std::filesystem::path path) : path_(std::move(path)) {
    if (!path_.parent_path().empty()) {
        std::filesystem::create_directories(path_.parent_path());
    }
    const int rc = sqlite3_open(path_.string().c_str(), &db_);
    if (rc != SQLITE_OK) {
        const std::string message = db_ ? sqlite3_errmsg(db_) : "sqlite open failed";
        if (db_) sqlite3_close(db_);
        db_ = nullptr;
        throw std::runtime_error(message);
    }
    exec_sql(db_, "PRAGMA foreign_keys = ON;");
    initialize();
}

ProofMemory::~ProofMemory() {
    if (db_) sqlite3_close(db_);
}

void ProofMemory::initialize() {
    exec_sql(db_, R"SQL(
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS proof_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_hash TEXT NOT NULL,
            goal_statement TEXT NOT NULL,
            tactic TEXT NOT NULL,
            success INTEGER NOT NULL CHECK(success IN (0, 1)),
            exit_code INTEGER NOT NULL,
            output_sha256 TEXT NOT NULL,
            output_excerpt TEXT NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_proof_attempts_goal
            ON proof_attempts(goal_hash);

        CREATE INDEX IF NOT EXISTS idx_proof_attempts_goal_tactic
            ON proof_attempts(goal_hash, tactic);
    )SQL");

    Statement select(db_, "SELECT value FROM metadata WHERE key = 'schema_version';");
    const int rc = sqlite3_step(select.get());
    check_sql(rc, db_, "read schema version");
    if (rc == SQLITE_DONE) {
        Statement insert(db_, "INSERT INTO metadata(key, value) VALUES('schema_version', ?);");
        check_sql(sqlite3_bind_text(insert.get(), 1, "1", -1, SQLITE_STATIC), db_, "bind schema");
        check_sql(sqlite3_step(insert.get()), db_, "insert schema");
    } else {
        const auto* value = reinterpret_cast<const char*>(sqlite3_column_text(select.get(), 0));
        if (!value || std::string(value) != std::to_string(kSchemaVersion)) {
            throw std::runtime_error("unsupported proof memory schema version");
        }
    }
}

void ProofMemory::record_result(const SearchResult& result) {
    const std::string hash = goal_fingerprint(result.problem);
    exec_sql(db_, "BEGIN IMMEDIATE;");
    try {
        Statement insert(
            db_,
            "INSERT INTO proof_attempts("
            "goal_hash, goal_statement, tactic, success, exit_code, output_sha256, output_excerpt"
            ") VALUES (?, ?, ?, ?, ?, ?, ?);");

        for (const auto& attempt : result.attempts) {
            sqlite3_reset(insert.get());
            sqlite3_clear_bindings(insert.get());

            const std::string output_hash = sha256_hex(attempt.output);
            const std::string excerpt =
                attempt.output.size() <= 2000U
                    ? attempt.output
                    : attempt.output.substr(attempt.output.size() - 2000U);

            bind_text(db_, insert.get(), 1, hash);
            bind_text(db_, insert.get(), 2, result.problem.statement);
            bind_text(db_, insert.get(), 3, attempt.tactic);
            check_sql(sqlite3_bind_int(insert.get(), 4, attempt.success ? 1 : 0), db_, "bind success");
            check_sql(sqlite3_bind_int(insert.get(), 5, attempt.exit_code), db_, "bind exit code");
            bind_text(db_, insert.get(), 6, output_hash);
            bind_text(db_, insert.get(), 7, excerpt);
            check_sql(sqlite3_step(insert.get()), db_, "insert proof attempt");
        }
        exec_sql(db_, "COMMIT;");
    } catch (...) {
        exec_sql(db_, "ROLLBACK;");
        throw;
    }
}

std::vector<StrategyStats> ProofMemory::stats_for(const SearchProblem& problem) const {
    const std::string hash = goal_fingerprint(problem);
    Statement query(
        db_,
        "SELECT tactic,"
        " SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END),"
        " SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END)"
        " FROM proof_attempts WHERE goal_hash = ?"
        " GROUP BY tactic ORDER BY tactic;");
    bind_text(db_, query.get(), 1, hash);

    std::vector<StrategyStats> result;
    while (true) {
        const int rc = sqlite3_step(query.get());
        check_sql(rc, db_, "query proof stats");
        if (rc == SQLITE_DONE) break;
        const auto* tactic = reinterpret_cast<const char*>(sqlite3_column_text(query.get(), 0));
        result.push_back(StrategyStats{
            .tactic = tactic ? tactic : "",
            .successes = sqlite3_column_int(query.get(), 1),
            .failures = sqlite3_column_int(query.get(), 2),
        });
    }
    return result;
}

std::vector<std::string> ProofMemory::order_strategies(
    const SearchProblem& problem,
    const std::vector<std::string>& base_strategies) const {
    std::map<std::string, StrategyStats> known;
    for (const auto& stats : stats_for(problem)) {
        known.emplace(stats.tactic, stats);
    }

    struct Ranked {
        std::string tactic;
        std::tuple<int, int, int, std::size_t> key;
    };
    std::vector<Ranked> ranked;
    ranked.reserve(base_strategies.size());
    for (std::size_t i = 0; i < base_strategies.size(); ++i) {
        const auto it = known.find(base_strategies[i]);
        const StrategyStats stats =
            it == known.end() ? StrategyStats{base_strategies[i], 0, 0} : it->second;
        ranked.push_back({
            base_strategies[i],
            {
                stats.successes > 0 ? 0 : 1,
                -stats.successes,
                stats.failures,
                i,
            },
        });
    }
    std::stable_sort(ranked.begin(), ranked.end(), [](const Ranked& a, const Ranked& b) {
        return a.key < b.key;
    });

    std::vector<std::string> ordered;
    ordered.reserve(ranked.size());
    for (auto& item : ranked) ordered.push_back(std::move(item.tactic));
    return ordered;
}

ProofMemorySummary ProofMemory::summary() const {
    return ProofMemorySummary{
        .schema_version = kSchemaVersion,
        .attempts = scalar_int64(db_, "SELECT COUNT(*) FROM proof_attempts;"),
        .goals = scalar_int64(db_, "SELECT COUNT(DISTINCT goal_hash) FROM proof_attempts;"),
        .successful_attempts =
            scalar_int64(db_, "SELECT COUNT(*) FROM proof_attempts WHERE success = 1;"),
    };
}

MemoryGuidedProofSearch::MemoryGuidedProofSearch(
    std::vector<std::string> base_strategies,
    ILeanRunner& runner,
    ProofMemory& memory)
    : base_strategies_(std::move(base_strategies)), runner_(runner), memory_(memory) {
    if (base_strategies_.empty()) {
        throw std::invalid_argument("base_strategies must be non-empty");
    }
}

SearchResult MemoryGuidedProofSearch::search(const SearchProblem& problem) {
    const auto ordered = memory_.order_strategies(problem, base_strategies_);
    DeterministicProofSearch search(ordered, runner_);
    auto result = search.search(problem);
    memory_.record_result(result);
    return result;
}

} // namespace expert_robot
