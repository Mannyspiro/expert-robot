#include "expert_robot/skills/experimental_skill_store.hpp"

#include <sqlite3.h>

#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::skills {
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
            "prepare experimental skill statement");
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
        "bind experimental skill text");
}

std::string text_column(
    sqlite3_stmt* stmt,
    int index) {
    const auto* raw =
        reinterpret_cast<const char*>(
            sqlite3_column_text(stmt, index));
    return raw ? std::string(raw) : std::string{};
}

imagination::ImaginationLens decode_lens(int raw) {
    if (raw < 0 ||
        raw >= static_cast<int>(
            imagination::ImaginationLens::Count)) {
        throw std::runtime_error(
            "invalid imagination lens in experimental skill store");
    }
    return static_cast<imagination::ImaginationLens>(raw);
}

swarm::AgentRole decode_role(int raw) {
    if (raw < 0 ||
        raw > static_cast<int>(
            swarm::AgentRole::Synthesizer)) {
        throw std::runtime_error(
            "invalid agent role in experimental skill store");
    }
    return static_cast<swarm::AgentRole>(raw);
}

MathSkill row_to_skill(sqlite3_stmt* stmt) {
    return MathSkill{
        .skill_id = text_column(stmt, 0),
        .title = text_column(stmt, 1),
        .lens = decode_lens(
            sqlite3_column_int(stmt, 2)),
        .preferred_role = decode_role(
            sqlite3_column_int(stmt, 3)),
        .procedure = text_column(stmt, 4),
        .requires_lean_verification =
            sqlite3_column_int(stmt, 5) != 0,
        .stage = SkillStage::Experimental,
    };
}

void validate_experimental_skill(
    const MathSkill& skill) {
    if (skill.skill_id.empty() ||
        skill.title.empty() ||
        skill.procedure.empty()) {
        throw std::invalid_argument(
            "experimental skill fields must be non-empty");
    }
    if (skill.stage != SkillStage::Experimental) {
        throw std::invalid_argument(
            "experimental store accepts only experimental skills");
    }
    if (!skill.requires_lean_verification) {
        throw std::invalid_argument(
            "math skills must retain Lean verification requirement");
    }
    if (!skill.skill_id.starts_with("math.experimental.")) {
        throw std::invalid_argument(
            "self-proposed skill IDs must use math.experimental.* namespace");
    }
}

} // namespace

ExperimentalSkillStore::ExperimentalSkillStore(
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

ExperimentalSkillStore::~ExperimentalSkillStore() {
    if (db_) sqlite3_close(db_);
}

void ExperimentalSkillStore::initialize() {
    exec_sql(
        db_,
        R"SQL(
        CREATE TABLE IF NOT EXISTS experimental_skill_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS experimental_skills (
            skill_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            lens INTEGER NOT NULL,
            preferred_role INTEGER NOT NULL,
            procedure TEXT NOT NULL,
            requires_lean_verification INTEGER NOT NULL CHECK(
                requires_lean_verification = 1
            ),
            source TEXT NOT NULL,
            proposal_count INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        )SQL");

    Statement query(
        db_,
        "SELECT value FROM experimental_skill_metadata "
        "WHERE key='schema_version';");
    const int rc = sqlite3_step(query.get());
    check(rc, db_, "read experimental skill schema");

    if (rc == SQLITE_DONE) {
        Statement insert(
            db_,
            "INSERT INTO experimental_skill_metadata(key,value) "
            "VALUES('schema_version','1');");
        check(
            sqlite3_step(insert.get()),
            db_,
            "insert experimental skill schema");
    } else {
        const auto* raw =
            reinterpret_cast<const char*>(
                sqlite3_column_text(query.get(), 0));
        if (!raw ||
            std::string(raw) !=
                std::to_string(kSchemaVersion)) {
            throw std::runtime_error(
                "unsupported experimental skill schema");
        }
    }
}

void ExperimentalSkillStore::propose(
    MathSkill skill,
    std::string_view source) {
    validate_experimental_skill(skill);
    if (source.empty()) {
        throw std::invalid_argument(
            "experimental skill source must be non-empty");
    }

    Statement stmt(
        db_,
        R"SQL(
        INSERT INTO experimental_skills(
            skill_id,title,lens,preferred_role,procedure,
            requires_lean_verification,source,
            proposal_count,updated_at
        ) VALUES (?,?,?,?,?,?,?,1,CURRENT_TIMESTAMP)
        ON CONFLICT(skill_id) DO UPDATE SET
            proposal_count=proposal_count+1,
            updated_at=CURRENT_TIMESTAMP;
        )SQL");

    bind_text(db_, stmt.get(), 1, skill.skill_id);
    bind_text(db_, stmt.get(), 2, skill.title);
    check(
        sqlite3_bind_int(
            stmt.get(),
            3,
            static_cast<int>(skill.lens)),
        db_,
        "bind experimental skill lens");
    check(
        sqlite3_bind_int(
            stmt.get(),
            4,
            static_cast<int>(skill.preferred_role)),
        db_,
        "bind experimental skill role");
    bind_text(db_, stmt.get(), 5, skill.procedure);
    check(
        sqlite3_bind_int(
            stmt.get(),
            6,
            skill.requires_lean_verification ? 1 : 0),
        db_,
        "bind experimental skill verification");
    bind_text(db_, stmt.get(), 7, source);

    check(
        sqlite3_step(stmt.get()),
        db_,
        "insert experimental skill");
}

std::vector<MathSkill>
ExperimentalSkillStore::all() const {
    Statement stmt(
        db_,
        "SELECT skill_id,title,lens,preferred_role,procedure,"
        "requires_lean_verification FROM experimental_skills "
        "ORDER BY skill_id;");

    std::vector<MathSkill> result;
    while (true) {
        const int rc = sqlite3_step(stmt.get());
        check(rc, db_, "read experimental skills");
        if (rc == SQLITE_DONE) break;
        result.push_back(row_to_skill(stmt.get()));
    }
    return result;
}

MathSkill ExperimentalSkillStore::get(
    std::string_view skill_id) const {
    Statement stmt(
        db_,
        "SELECT skill_id,title,lens,preferred_role,procedure,"
        "requires_lean_verification FROM experimental_skills "
        "WHERE skill_id=?;");
    bind_text(db_, stmt.get(), 1, skill_id);

    const int rc = sqlite3_step(stmt.get());
    check(rc, db_, "read experimental skill");
    if (rc == SQLITE_DONE) {
        throw std::out_of_range(
            "unknown experimental skill: " +
            std::string(skill_id));
    }
    return row_to_skill(stmt.get());
}

SkillPromotionReport
ExperimentalSkillStore::promotion_report(
    std::string_view skill_id,
    const SkillLedger& ledger,
    const SkillQualificationPolicy& policy) const {
    const auto skill = get(skill_id);
    const auto stats = ledger.stats(skill_id);
    const auto recommendation =
        recommended_stage(stats, policy);

    std::string rationale;
    switch (recommendation) {
        case SkillStage::Qualified:
            rationale =
                "Evidence meets the configured qualification thresholds. "
                "An explicit registry/code promotion is still required.";
            break;
        case SkillStage::Deprecated:
            rationale =
                "Resolved evidence shows no verified downstream wins. "
                "Deprecation is recommended but remains an explicit change.";
            break;
        case SkillStage::Experimental:
            rationale =
                "Evidence is insufficient for qualification or deprecation.";
            break;
    }

    return SkillPromotionReport{
        .skill = skill,
        .stats = stats,
        .recommended = recommendation,
        .requires_explicit_promotion = true,
        .rationale = std::move(rationale),
    };
}

} // namespace expert_robot::skills
