#include "expert_robot/imagination/memory.hpp"

#include <sqlite3.h>

#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::imagination {
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
        check(
            sqlite3_prepare_v2(
                db_,
                sql,
                -1,
                &stmt_,
                nullptr),
            db_,
            "prepare imagination memory");
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
    check(
        sqlite3_bind_text(
            stmt,
            index,
            value.c_str(),
            static_cast<int>(value.size()),
            SQLITE_TRANSIENT),
        db,
        "bind imagination text");
}

} // namespace

ImaginationMemory::ImaginationMemory(
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

ImaginationMemory::~ImaginationMemory() {
    if (db_) sqlite3_close(db_);
}

void ImaginationMemory::initialize() {
    exec_sql(
        db_,
        R"SQL(
        CREATE TABLE IF NOT EXISTS imagination_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS imagination_ideas (
            idea_id TEXT PRIMARY KEY,
            lens INTEGER NOT NULL,
            source_role INTEGER NOT NULL,
            text TEXT NOT NULL,
            novelty_score REAL NOT NULL,
            relevance_score REAL NOT NULL,
            qd_score REAL NOT NULL,
            skeptic_valid INTEGER NOT NULL,
            skeptic_keep INTEGER NOT NULL,
            skeptic_risk INTEGER NOT NULL,
            skeptic_critique TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_imagination_lens
            ON imagination_ideas(lens);
        )SQL");

    Statement select(
        db_,
        "SELECT value FROM imagination_metadata "
        "WHERE key='schema_version';");

    const int rc =
        sqlite3_step(select.get());
    check(
        rc,
        db_,
        "read imagination schema");

    if (rc == SQLITE_DONE) {
        Statement insert(
            db_,
            "INSERT INTO imagination_metadata(key,value) "
            "VALUES('schema_version', ?);");
        check(
            sqlite3_bind_text(
                insert.get(),
                1,
                "1",
                -1,
                SQLITE_STATIC),
            db_,
            "bind imagination schema");
        check(
            sqlite3_step(insert.get()),
            db_,
            "insert imagination schema");
    } else {
        const auto* raw =
            reinterpret_cast<const char*>(
                sqlite3_column_text(
                    select.get(),
                    0));
        if (!raw ||
            std::string(raw) !=
                std::to_string(kSchemaVersion)) {
            throw std::runtime_error(
                "unsupported imagination memory schema");
        }
    }
}

void ImaginationMemory::upsert(
    const IdeaCandidate& idea) {
    if (idea.idea_id.empty() ||
        idea.text.empty()) {
        throw std::invalid_argument(
            "imagination memory requires idea id and text");
    }

    Statement stmt(
        db_,
        R"SQL(
        INSERT INTO imagination_ideas(
            idea_id, lens, source_role, text,
            novelty_score, relevance_score, qd_score,
            skeptic_valid, skeptic_keep, skeptic_risk,
            skeptic_critique, seen_count, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(idea_id) DO UPDATE SET
            novelty_score=MAX(novelty_score, excluded.novelty_score),
            relevance_score=MAX(relevance_score, excluded.relevance_score),
            qd_score=MAX(qd_score, excluded.qd_score),
            skeptic_valid=MAX(skeptic_valid, excluded.skeptic_valid),
            skeptic_keep=MAX(skeptic_keep, excluded.skeptic_keep),
            skeptic_risk=MIN(skeptic_risk, excluded.skeptic_risk),
            skeptic_critique=
                CASE
                    WHEN excluded.skeptic_critique <> ''
                    THEN excluded.skeptic_critique
                    ELSE skeptic_critique
                END,
            seen_count=seen_count + 1,
            updated_at=CURRENT_TIMESTAMP;
        )SQL");

    bind_text(
        db_,
        stmt.get(),
        1,
        idea.idea_id);
    check(
        sqlite3_bind_int(
            stmt.get(),
            2,
            static_cast<int>(idea.lens)),
        db_,
        "bind idea lens");
    check(
        sqlite3_bind_int(
            stmt.get(),
            3,
            static_cast<int>(idea.source_role)),
        db_,
        "bind idea role");
    bind_text(
        db_,
        stmt.get(),
        4,
        idea.text);
    check(
        sqlite3_bind_double(
            stmt.get(),
            5,
            idea.novelty_score),
        db_,
        "bind idea novelty");
    check(
        sqlite3_bind_double(
            stmt.get(),
            6,
            idea.relevance_score),
        db_,
        "bind idea relevance");
    check(
        sqlite3_bind_double(
            stmt.get(),
            7,
            idea.quality_diversity_score),
        db_,
        "bind idea qd");
    check(
        sqlite3_bind_int(
            stmt.get(),
            8,
            idea.skeptic_valid ? 1 : 0),
        db_,
        "bind idea skeptic valid");
    check(
        sqlite3_bind_int(
            stmt.get(),
            9,
            idea.skeptic_keep ? 1 : 0),
        db_,
        "bind idea skeptic keep");
    check(
        sqlite3_bind_int(
            stmt.get(),
            10,
            idea.skeptic_risk),
        db_,
        "bind idea risk");
    bind_text(
        db_,
        stmt.get(),
        11,
        idea.skeptic_critique);

    check(
        sqlite3_step(stmt.get()),
        db_,
        "upsert imagination idea");
}

std::vector<IdeaCandidate>
ImaginationMemory::all() const {
    Statement stmt(
        db_,
        R"SQL(
        SELECT
            idea_id, lens, source_role, text,
            novelty_score, relevance_score, qd_score,
            skeptic_valid, skeptic_keep, skeptic_risk,
            skeptic_critique
        FROM imagination_ideas
        ORDER BY updated_at, idea_id;
        )SQL");

    std::vector<IdeaCandidate> result;

    while (true) {
        const int rc =
            sqlite3_step(stmt.get());
        check(
            rc,
            db_,
            "read imagination ideas");
        if (rc == SQLITE_DONE) break;

        const int lens =
            sqlite3_column_int(
                stmt.get(),
                1);
        const int role =
            sqlite3_column_int(
                stmt.get(),
                2);

        if (lens < 0 ||
            lens >= static_cast<int>(
                ImaginationLens::Count)) {
            throw std::runtime_error(
                "invalid lens stored in imagination memory");
        }
        if (role < 0 ||
            role > static_cast<int>(
                swarm::AgentRole::Synthesizer)) {
            throw std::runtime_error(
                "invalid agent role stored in imagination memory");
        }

        const auto text_col = [&](int index) {
            const auto* raw =
                reinterpret_cast<const char*>(
                    sqlite3_column_text(
                        stmt.get(),
                        index));
            return raw
                ? std::string(raw)
                : std::string{};
        };

        result.push_back(
            IdeaCandidate{
                .idea_id = text_col(0),
                .lens =
                    static_cast<ImaginationLens>(lens),
                .source_role =
                    static_cast<swarm::AgentRole>(role),
                .text = text_col(3),
                .skill_id = {},
                .novelty_score =
                    sqlite3_column_double(
                        stmt.get(),
                        4),
                .relevance_score =
                    sqlite3_column_double(
                        stmt.get(),
                        5),
                .quality_diversity_score =
                    sqlite3_column_double(
                        stmt.get(),
                        6),
                .skeptic_valid =
                    sqlite3_column_int(
                        stmt.get(),
                        7) != 0,
                .skeptic_keep =
                    sqlite3_column_int(
                        stmt.get(),
                        8) != 0,
                .skeptic_risk =
                    sqlite3_column_int(
                        stmt.get(),
                        9),
                .skeptic_critique =
                    text_col(10),
            });
    }

    return result;
}

long long ImaginationMemory::count() const {
    Statement stmt(
        db_,
        "SELECT COUNT(*) FROM imagination_ideas;");
    const int rc =
        sqlite3_step(stmt.get());
    check(
        rc,
        db_,
        "count imagination ideas");
    return rc == SQLITE_ROW
        ? sqlite3_column_int64(
              stmt.get(),
              0)
        : 0;
}

} // namespace expert_robot::imagination
