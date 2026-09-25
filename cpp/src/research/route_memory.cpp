#include "expert_robot/research/route_memory.hpp"

#include <sqlite3.h>

#include <cmath>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::research {
namespace {

constexpr int kSchemaVersion = 1;

void check_sql(
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

void exec_sql(
    sqlite3* db,
    const char* sql) {
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
    Statement(
        sqlite3* db,
        const char* sql)
        : db_(db) {
        check_sql(
            sqlite3_prepare_v2(
                db_,
                sql,
                -1,
                &stmt_,
                nullptr),
            db_,
            "prepare route memory statement");
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
    const std::string& value) {
    check_sql(
        sqlite3_bind_text(
            stmt,
            index,
            value.c_str(),
            static_cast<int>(value.size()),
            SQLITE_TRANSIENT),
        db,
        "bind route memory text");
}

std::string column_text(
    sqlite3_stmt* stmt,
    int index) {
    const auto* raw =
        reinterpret_cast<const char*>(
            sqlite3_column_text(
                stmt,
                index));
    return raw ? std::string(raw) : std::string{};
}

void validate_outcome(
    const RouteOutcome& outcome) {
    if (outcome.route_id.empty()) {
        throw std::invalid_argument(
            "route outcome route_id must be non-empty");
    }
    if (outcome.domain.empty()) {
        throw std::invalid_argument(
            "route outcome domain must be non-empty");
    }
    if (!std::isfinite(outcome.resource_cost) ||
        outcome.resource_cost < 0.0) {
        throw std::invalid_argument(
            "route outcome resource_cost must be finite and nonnegative");
    }
}

void validate_sequence_outcome(
    const RouteSequenceOutcome& outcome) {
    if (outcome.sequence_id.empty()) {
        throw std::invalid_argument(
            "route sequence outcome sequence_id must be non-empty");
    }
    if (outcome.domain.empty()) {
        throw std::invalid_argument(
            "route sequence outcome domain must be non-empty");
    }
    if (!std::isfinite(outcome.resource_cost) ||
        outcome.resource_cost < 0.0) {
        throw std::invalid_argument(
            "route sequence outcome resource_cost must be finite and nonnegative");
    }
}

void validate_strategy_outcome(
    const ResearchStrategyOutcome& outcome) {
    if (outcome.strategy_id.empty()) {
        throw std::invalid_argument(
            "research strategy outcome strategy_id must be non-empty");
    }
    if (outcome.signature.empty()) {
        throw std::invalid_argument(
            "research strategy outcome signature must be non-empty");
    }
    if (outcome.domain.empty()) {
        throw std::invalid_argument(
            "research strategy outcome domain must be non-empty");
    }
    if (!std::isfinite(outcome.resource_cost) ||
        outcome.resource_cost < 0.0) {
        throw std::invalid_argument(
            "research strategy outcome resource_cost must be finite and nonnegative");
    }
}

void validate_strategy_context_outcome(
    const ResearchStrategyContextOutcome& outcome) {
    if (outcome.strategy_id.empty() ||
        outcome.signature.empty() ||
        outcome.context_key.empty()) {
        throw std::invalid_argument(
            "research strategy context outcome identifiers must be non-empty");
    }
    if (!std::isfinite(outcome.resource_cost) ||
        outcome.resource_cost < 0.0) {
        throw std::invalid_argument(
            "research strategy context resource_cost must be finite and nonnegative");
    }
}

RouteExperience read_experience(
    sqlite3_stmt* stmt) {
    return RouteExperience{
        .kind =
            static_cast<ProofRouteKind>(
                sqlite3_column_int(
                    stmt,
                    0)),
        .domain =
            column_text(stmt, 1),
        .attempts =
            sqlite3_column_int64(
                stmt,
                2),
        .verified_progresses =
            sqlite3_column_int64(
                stmt,
                3),
        .target_verifications =
            sqlite3_column_int64(
                stmt,
                4),
        .dead_end_escapes =
            sqlite3_column_int64(
                stmt,
                5),
        .total_resource_cost =
            sqlite3_column_double(
                stmt,
                6),
    };
}

RouteSequenceExperience read_sequence_experience(
    sqlite3_stmt* stmt) {
    return RouteSequenceExperience{
        .sequence_id =
            column_text(stmt, 0),
        .domain =
            column_text(stmt, 1),
        .attempts =
            sqlite3_column_int64(
                stmt,
                2),
        .verified_progresses =
            sqlite3_column_int64(
                stmt,
                3),
        .target_verifications =
            sqlite3_column_int64(
                stmt,
                4),
        .dead_end_escapes =
            sqlite3_column_int64(
                stmt,
                5),
        .total_resource_cost =
            sqlite3_column_double(
                stmt,
                6),
    };
}

ResearchStrategyExperience read_strategy_experience(
    sqlite3_stmt* stmt) {
    return ResearchStrategyExperience{
        .strategy_id =
            column_text(stmt, 0),
        .signature =
            column_text(stmt, 1),
        .domain =
            column_text(stmt, 2),
        .attempts =
            sqlite3_column_int64(
                stmt,
                3),
        .verified_progresses =
            sqlite3_column_int64(
                stmt,
                4),
        .target_verifications =
            sqlite3_column_int64(
                stmt,
                5),
        .dead_end_escapes =
            sqlite3_column_int64(
                stmt,
                6),
        .total_resource_cost =
            sqlite3_column_double(
                stmt,
                7),
    };
}

ResearchStrategyContextExperience
read_strategy_context_experience(
    sqlite3_stmt* stmt) {
    return ResearchStrategyContextExperience{
        .strategy_id =
            column_text(stmt, 0),
        .signature =
            column_text(stmt, 1),
        .context_key =
            column_text(stmt, 2),
        .attempts =
            sqlite3_column_int64(
                stmt,
                3),
        .verified_progresses =
            sqlite3_column_int64(
                stmt,
                4),
        .target_verifications =
            sqlite3_column_int64(
                stmt,
                5),
        .dead_end_escapes =
            sqlite3_column_int64(
                stmt,
                6),
        .total_resource_cost =
            sqlite3_column_double(
                stmt,
                7),
    };
}

} // namespace

double RouteExperience::smoothed_verified_rate() const noexcept {
    // Beta(1,1) prior prevents early single successes/failures from dominating.
    return
        (static_cast<double>(verified_progresses) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double RouteExperience::smoothed_target_rate() const noexcept {
    return
        (static_cast<double>(target_verifications) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double RouteExperience::average_resource_cost() const noexcept {
    return attempts > 0
        ? total_resource_cost /
              static_cast<double>(attempts)
        : 0.0;
}

double RouteSequenceExperience::smoothed_verified_rate() const noexcept {
    return
        (static_cast<double>(verified_progresses) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double RouteSequenceExperience::smoothed_target_rate() const noexcept {
    return
        (static_cast<double>(target_verifications) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double RouteSequenceExperience::average_resource_cost() const noexcept {
    return attempts > 0
        ? total_resource_cost /
              static_cast<double>(attempts)
        : 0.0;
}

double ResearchStrategyExperience::smoothed_verified_rate() const noexcept {
    return
        (static_cast<double>(verified_progresses) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double ResearchStrategyExperience::smoothed_target_rate() const noexcept {
    return
        (static_cast<double>(target_verifications) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double ResearchStrategyExperience::average_resource_cost() const noexcept {
    return attempts > 0
        ? total_resource_cost /
              static_cast<double>(attempts)
        : 0.0;
}

double ResearchStrategyContextExperience::smoothed_verified_rate() const noexcept {
    return
        (static_cast<double>(verified_progresses) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double ResearchStrategyContextExperience::smoothed_target_rate() const noexcept {
    return
        (static_cast<double>(target_verifications) + 1.0) /
        (static_cast<double>(attempts) + 2.0);
}

double ResearchStrategyContextExperience::average_resource_cost() const noexcept {
    return attempts > 0
        ? total_resource_cost /
              static_cast<double>(attempts)
        : 0.0;
}

RouteOutcomeLedger::RouteOutcomeLedger(
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

RouteOutcomeLedger::~RouteOutcomeLedger() {
    if (db_) sqlite3_close(db_);
}

void RouteOutcomeLedger::initialize() {
    exec_sql(
        db_,
        R"SQL(
        CREATE TABLE IF NOT EXISTS route_memory_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS route_outcomes (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            route_id TEXT NOT NULL,
            kind INTEGER NOT NULL,
            domain TEXT NOT NULL,
            verified_progress INTEGER NOT NULL,
            target_verified INTEGER NOT NULL,
            dead_end_escaped INTEGER NOT NULL,
            resource_cost REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_route_outcomes_kind_domain
            ON route_outcomes(kind, domain);

        CREATE TABLE IF NOT EXISTS route_sequence_outcomes (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence_id TEXT NOT NULL,
            domain TEXT NOT NULL,
            verified_progress INTEGER NOT NULL,
            target_verified INTEGER NOT NULL,
            dead_end_escaped INTEGER NOT NULL,
            resource_cost REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_route_sequence_outcomes_id_domain
            ON route_sequence_outcomes(sequence_id, domain);

        CREATE TABLE IF NOT EXISTS research_strategy_outcomes (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id TEXT NOT NULL,
            signature TEXT NOT NULL,
            domain TEXT NOT NULL,
            verified_progress INTEGER NOT NULL,
            target_verified INTEGER NOT NULL,
            dead_end_escaped INTEGER NOT NULL,
            resource_cost REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_research_strategy_outcomes_id_domain
            ON research_strategy_outcomes(strategy_id, domain);

        CREATE TABLE IF NOT EXISTS research_strategy_context_outcomes (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id TEXT NOT NULL,
            signature TEXT NOT NULL,
            context_key TEXT NOT NULL,
            verified_progress INTEGER NOT NULL,
            target_verified INTEGER NOT NULL,
            dead_end_escaped INTEGER NOT NULL,
            resource_cost REAL NOT NULL,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_research_strategy_context
            ON research_strategy_context_outcomes(strategy_id, context_key);
        )SQL");

    Statement query(
        db_,
        "SELECT value FROM route_memory_metadata "
        "WHERE key='schema_version';");

    const int rc =
        sqlite3_step(query.get());
    check_sql(
        rc,
        db_,
        "read route memory schema");

    if (rc == SQLITE_DONE) {
        Statement insert(
            db_,
            "INSERT INTO route_memory_metadata(key,value) "
            "VALUES('schema_version','1');");
        check_sql(
            sqlite3_step(insert.get()),
            db_,
            "insert route memory schema");
    } else if (
        column_text(query.get(), 0) !=
        std::to_string(kSchemaVersion)) {
        throw std::runtime_error(
            "unsupported route memory schema");
    }
}

void RouteOutcomeLedger::record(
    const RouteOutcome& outcome) {
    validate_outcome(outcome);

    Statement insert(
        db_,
        R"SQL(
        INSERT INTO route_outcomes(
            route_id,
            kind,
            domain,
            verified_progress,
            target_verified,
            dead_end_escaped,
            resource_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        )SQL");

    bind_text(db_, insert.get(), 1, outcome.route_id);
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            2,
            static_cast<int>(outcome.kind)),
        db_,
        "bind route kind");
    bind_text(db_, insert.get(), 3, outcome.domain);
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            4,
            outcome.verified_progress ? 1 : 0),
        db_,
        "bind verified progress");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            5,
            outcome.target_verified ? 1 : 0),
        db_,
        "bind target verified");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            6,
            outcome.dead_end_escaped ? 1 : 0),
        db_,
        "bind dead end escape");
    check_sql(
        sqlite3_bind_double(
            insert.get(),
            7,
            outcome.resource_cost),
        db_,
        "bind resource cost");

    check_sql(
        sqlite3_step(insert.get()),
        db_,
        "insert route outcome");
}

void RouteOutcomeLedger::record_sequence(
    const RouteSequenceOutcome& outcome) {
    validate_sequence_outcome(outcome);

    Statement insert(
        db_,
        R"SQL(
        INSERT INTO route_sequence_outcomes(
            sequence_id,
            domain,
            verified_progress,
            target_verified,
            dead_end_escaped,
            resource_cost
        ) VALUES (?, ?, ?, ?, ?, ?);
        )SQL");

    bind_text(
        db_,
        insert.get(),
        1,
        outcome.sequence_id);
    bind_text(
        db_,
        insert.get(),
        2,
        outcome.domain);
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            3,
            outcome.verified_progress ? 1 : 0),
        db_,
        "bind sequence verified progress");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            4,
            outcome.target_verified ? 1 : 0),
        db_,
        "bind sequence target verified");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            5,
            outcome.dead_end_escaped ? 1 : 0),
        db_,
        "bind sequence dead end escape");
    check_sql(
        sqlite3_bind_double(
            insert.get(),
            6,
            outcome.resource_cost),
        db_,
        "bind sequence resource cost");

    check_sql(
        sqlite3_step(insert.get()),
        db_,
        "insert route sequence outcome");
}

void RouteOutcomeLedger::record_strategy(
    const ResearchStrategyOutcome& outcome) {
    validate_strategy_outcome(outcome);

    Statement insert(
        db_,
        R"SQL(
        INSERT INTO research_strategy_outcomes(
            strategy_id,
            signature,
            domain,
            verified_progress,
            target_verified,
            dead_end_escaped,
            resource_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        )SQL");

    bind_text(
        db_,
        insert.get(),
        1,
        outcome.strategy_id);
    bind_text(
        db_,
        insert.get(),
        2,
        outcome.signature);
    bind_text(
        db_,
        insert.get(),
        3,
        outcome.domain);
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            4,
            outcome.verified_progress ? 1 : 0),
        db_,
        "bind strategy verified progress");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            5,
            outcome.target_verified ? 1 : 0),
        db_,
        "bind strategy target verified");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            6,
            outcome.dead_end_escaped ? 1 : 0),
        db_,
        "bind strategy dead end escape");
    check_sql(
        sqlite3_bind_double(
            insert.get(),
            7,
            outcome.resource_cost),
        db_,
        "bind strategy resource cost");

    check_sql(
        sqlite3_step(insert.get()),
        db_,
        "insert research strategy outcome");
}

void RouteOutcomeLedger::record_strategy_context(
    const ResearchStrategyContextOutcome& outcome) {
    validate_strategy_context_outcome(outcome);

    Statement insert(
        db_,
        R"SQL(
        INSERT INTO research_strategy_context_outcomes(
            strategy_id,
            signature,
            context_key,
            verified_progress,
            target_verified,
            dead_end_escaped,
            resource_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        )SQL");

    bind_text(db_, insert.get(), 1, outcome.strategy_id);
    bind_text(db_, insert.get(), 2, outcome.signature);
    bind_text(db_, insert.get(), 3, outcome.context_key);
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            4,
            outcome.verified_progress ? 1 : 0),
        db_,
        "bind strategy context verified progress");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            5,
            outcome.target_verified ? 1 : 0),
        db_,
        "bind strategy context target verified");
    check_sql(
        sqlite3_bind_int(
            insert.get(),
            6,
            outcome.dead_end_escaped ? 1 : 0),
        db_,
        "bind strategy context dead end escape");
    check_sql(
        sqlite3_bind_double(
            insert.get(),
            7,
            outcome.resource_cost),
        db_,
        "bind strategy context resource cost");

    check_sql(
        sqlite3_step(insert.get()),
        db_,
        "insert research strategy context outcome");
}

RouteExperience RouteOutcomeLedger::experience(
    ProofRouteKind kind,
    std::string_view domain) const {
    if (domain.empty()) {
        throw std::invalid_argument(
            "route experience domain must be non-empty");
    }

    Statement query(
        db_,
        R"SQL(
        SELECT
            kind,
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM route_outcomes
        WHERE kind = ? AND domain = ?
        GROUP BY kind, domain;
        )SQL");

    check_sql(
        sqlite3_bind_int(
            query.get(),
            1,
            static_cast<int>(kind)),
        db_,
        "bind experience kind");
    bind_text(
        db_,
        query.get(),
        2,
        std::string(domain));

    const int rc =
        sqlite3_step(query.get());
    check_sql(
        rc,
        db_,
        "read route experience");

    if (rc == SQLITE_DONE) {
        return RouteExperience{
            .kind = kind,
            .domain = std::string(domain),
        };
    }

    return read_experience(
        query.get());
}

std::vector<RouteExperience>
RouteOutcomeLedger::all_experience() const {
    Statement query(
        db_,
        R"SQL(
        SELECT
            kind,
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM route_outcomes
        GROUP BY kind, domain
        ORDER BY domain, kind;
        )SQL");

    std::vector<RouteExperience> result;
    while (true) {
        const int rc =
            sqlite3_step(query.get());
        check_sql(
            rc,
            db_,
            "list route experience");
        if (rc == SQLITE_DONE) break;
        result.push_back(
            read_experience(
                query.get()));
    }
    return result;
}

RouteSequenceExperience
RouteOutcomeLedger::sequence_experience(
    std::string_view sequence_id,
    std::string_view domain) const {
    if (sequence_id.empty() ||
        domain.empty()) {
        throw std::invalid_argument(
            "route sequence experience id/domain must be non-empty");
    }

    Statement query(
        db_,
        R"SQL(
        SELECT
            sequence_id,
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM route_sequence_outcomes
        WHERE sequence_id = ? AND domain = ?
        GROUP BY sequence_id, domain;
        )SQL");

    bind_text(
        db_,
        query.get(),
        1,
        std::string(sequence_id));
    bind_text(
        db_,
        query.get(),
        2,
        std::string(domain));

    const int rc =
        sqlite3_step(query.get());
    check_sql(
        rc,
        db_,
        "read route sequence experience");

    if (rc == SQLITE_DONE) {
        return RouteSequenceExperience{
            .sequence_id =
                std::string(sequence_id),
            .domain =
                std::string(domain),
        };
    }

    return read_sequence_experience(
        query.get());
}

std::vector<RouteSequenceExperience>
RouteOutcomeLedger::all_sequence_experience() const {
    Statement query(
        db_,
        R"SQL(
        SELECT
            sequence_id,
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM route_sequence_outcomes
        GROUP BY sequence_id, domain
        ORDER BY domain, sequence_id;
        )SQL");

    std::vector<RouteSequenceExperience> result;
    while (true) {
        const int rc =
            sqlite3_step(query.get());
        check_sql(
            rc,
            db_,
            "list route sequence experience");
        if (rc == SQLITE_DONE) break;

        result.push_back(
            read_sequence_experience(
                query.get()));
    }

    return result;
}

ResearchStrategyExperience
RouteOutcomeLedger::strategy_experience(
    std::string_view strategy_id,
    std::string_view domain) const {
    if (strategy_id.empty() ||
        domain.empty()) {
        throw std::invalid_argument(
            "research strategy experience id/domain must be non-empty");
    }

    Statement query(
        db_,
        R"SQL(
        SELECT
            strategy_id,
            MIN(signature),
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM research_strategy_outcomes
        WHERE strategy_id = ? AND domain = ?
        GROUP BY strategy_id, domain;
        )SQL");

    bind_text(
        db_,
        query.get(),
        1,
        std::string(strategy_id));
    bind_text(
        db_,
        query.get(),
        2,
        std::string(domain));

    const int rc =
        sqlite3_step(query.get());
    check_sql(
        rc,
        db_,
        "read research strategy experience");

    if (rc == SQLITE_DONE) {
        return ResearchStrategyExperience{
            .strategy_id =
                std::string(strategy_id),
            .domain =
                std::string(domain),
        };
    }

    return read_strategy_experience(
        query.get());
}

std::vector<ResearchStrategyExperience>
RouteOutcomeLedger::all_strategy_experience() const {
    Statement query(
        db_,
        R"SQL(
        SELECT
            strategy_id,
            MIN(signature),
            domain,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM research_strategy_outcomes
        GROUP BY strategy_id, domain
        ORDER BY domain, strategy_id;
        )SQL");

    std::vector<ResearchStrategyExperience> result;
    while (true) {
        const int rc =
            sqlite3_step(query.get());
        check_sql(
            rc,
            db_,
            "list research strategy experience");
        if (rc == SQLITE_DONE) break;

        result.push_back(
            read_strategy_experience(
                query.get()));
    }

    return result;
}

ResearchStrategyContextExperience
RouteOutcomeLedger::strategy_context_experience(
    std::string_view strategy_id,
    std::string_view context_key) const {
    if (strategy_id.empty() ||
        context_key.empty()) {
        throw std::invalid_argument(
            "strategy context experience id/key must be non-empty");
    }

    Statement query(
        db_,
        R"SQL(
        SELECT
            strategy_id,
            MIN(signature),
            context_key,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM research_strategy_context_outcomes
        WHERE strategy_id = ? AND context_key = ?
        GROUP BY strategy_id, context_key;
        )SQL");

    bind_text(
        db_,
        query.get(),
        1,
        std::string(strategy_id));
    bind_text(
        db_,
        query.get(),
        2,
        std::string(context_key));

    const int rc =
        sqlite3_step(query.get());
    check_sql(
        rc,
        db_,
        "read strategy context experience");

    if (rc == SQLITE_DONE) {
        return ResearchStrategyContextExperience{
            .strategy_id =
                std::string(strategy_id),
            .context_key =
                std::string(context_key),
        };
    }

    return read_strategy_context_experience(
        query.get());
}

std::vector<ResearchStrategyContextExperience>
RouteOutcomeLedger::all_strategy_context_experience() const {
    Statement query(
        db_,
        R"SQL(
        SELECT
            strategy_id,
            MIN(signature),
            context_key,
            COUNT(*),
            SUM(verified_progress),
            SUM(target_verified),
            SUM(dead_end_escaped),
            COALESCE(SUM(resource_cost), 0.0)
        FROM research_strategy_context_outcomes
        GROUP BY strategy_id, context_key
        ORDER BY context_key, strategy_id;
        )SQL");

    std::vector<ResearchStrategyContextExperience> result;
    while (true) {
        const int rc =
            sqlite3_step(query.get());
        check_sql(
            rc,
            db_,
            "list strategy context experience");
        if (rc == SQLITE_DONE) break;

        result.push_back(
            read_strategy_context_experience(
                query.get()));
    }

    return result;
}

} // namespace expert_robot::research
