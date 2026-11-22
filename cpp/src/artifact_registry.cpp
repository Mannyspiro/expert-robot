#include "expert_robot/artifact_registry.hpp"

#include "expert_robot/sha256.hpp"

#include <sqlite3.h>

#include <algorithm>
#include <cctype>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>

namespace expert_robot::artifacts {
namespace {

constexpr int kSchemaVersion = 1;
constexpr std::size_t kMaxMetadataBytes = 1024U * 1024U;

void check(int code, sqlite3* db, const char* context) {
    if (code != SQLITE_OK && code != SQLITE_DONE && code != SQLITE_ROW) {
        throw std::runtime_error(
            std::string(context) + ": " +
            (db ? sqlite3_errmsg(db) : "sqlite error"));
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

class Statement {
public:
    Statement(sqlite3* db, const char* sql) : db_(db) {
        check(sqlite3_prepare_v2(db_, sql, -1, &stmt_, nullptr),
              db_, "prepare artifact registry statement");
    }

    ~Statement() {
        if (stmt_) sqlite3_finalize(stmt_);
    }

    sqlite3_stmt* get() const noexcept { return stmt_; }

private:
    sqlite3* db_{nullptr};
    sqlite3_stmt* stmt_{nullptr};
};

void bind_text(sqlite3* db, sqlite3_stmt* stmt, int index, std::string_view value) {
    check(sqlite3_bind_text(stmt, index, value.data(),
                            static_cast<int>(value.size()), SQLITE_TRANSIENT),
          db, "bind artifact registry text");
}

std::string text_column(sqlite3_stmt* stmt, int index) {
    const auto* raw = reinterpret_cast<const char*>(sqlite3_column_text(stmt, index));
    const int bytes = sqlite3_column_bytes(stmt, index);
    return raw && bytes > 0 ? std::string(raw, static_cast<std::size_t>(bytes))
                            : std::string{};
}

bool is_lower_hex(std::string_view value, std::size_t exact_size) {
    if (value.size() != exact_size) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    });
}

bool is_commit_hex(std::string_view value) {
    if (value.size() != 40U && value.size() != 64U) return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isxdigit(ch) != 0;
    });
}

void require_text(std::string_view value, const char* field) {
    if (value.empty()) {
        throw std::invalid_argument(std::string(field) + " must be non-empty");
    }
    if (value.size() > kMaxMetadataBytes) {
        throw std::invalid_argument(std::string(field) + " exceeds metadata size limit");
    }
}

void validate_artifact(const ArtifactRecord& artifact) {
    require_text(artifact.artifact_id, "artifact_id");
    require_text(artifact.artifact_type, "artifact_type");
    require_text(artifact.media_type, "media_type");
    require_text(artifact.content_sha256, "content_sha256");
    require_text(artifact.locator, "locator");
    require_text(artifact.producer, "producer");
    require_text(artifact.producer_version, "producer_version");
    require_text(artifact.provenance_json, "provenance_json");

    if (!is_lower_hex(artifact.content_sha256, 64U)) {
        throw std::invalid_argument("content_sha256 must be 64 lowercase hexadecimal characters");
    }
    if ((artifact.source_repository.empty()) != artifact.source_commit.empty()) {
        throw std::invalid_argument("source_repository and source_commit must be supplied together");
    }
    if (!artifact.source_commit.empty() && !is_commit_hex(artifact.source_commit)) {
        throw std::invalid_argument("source_commit must be a 40- or 64-character hexadecimal commit");
    }
    if (artifact.size_bytes >
        static_cast<std::uint64_t>(std::numeric_limits<sqlite3_int64>::max())) {
        throw std::invalid_argument("size_bytes exceeds SQLite integer range");
    }
}

std::string verdict_text(VerificationVerdict verdict) {
    return std::string(verification_verdict_name(verdict));
}

VerificationVerdict parse_verdict(std::string_view value) {
    if (value == "verified") return VerificationVerdict::Verified;
    if (value == "rejected") return VerificationVerdict::Rejected;
    throw std::runtime_error("unknown artifact verification verdict in database");
}

void append_field(std::string& target, std::string_view value) {
    target += std::to_string(value.size());
    target.push_back(':');
    target.append(value);
}

std::string receipt_hash_material(const VerificationReceipt& receipt) {
    std::string material;
    append_field(material, std::to_string(receipt.sequence));
    append_field(material, receipt.receipt_id);
    append_field(material, receipt.artifact_id);
    append_field(material, receipt.verifier_id);
    append_field(material, receipt.verifier_version);
    append_field(material, verdict_text(receipt.verdict));
    append_field(material, receipt.artifact_sha256);
    append_field(material, receipt.evidence_json);
    append_field(material, receipt.previous_receipt_hash);
    return material;
}

VerificationReceipt row_to_receipt(sqlite3_stmt* stmt) {
    VerificationReceipt result;
    result.sequence = sqlite3_column_int64(stmt, 0);
    result.receipt_id = text_column(stmt, 1);
    result.artifact_id = text_column(stmt, 2);
    result.verifier_id = text_column(stmt, 3);
    result.verifier_version = text_column(stmt, 4);
    result.verdict = parse_verdict(text_column(stmt, 5));
    result.artifact_sha256 = text_column(stmt, 6);
    result.evidence_json = text_column(stmt, 7);
    result.previous_receipt_hash = text_column(stmt, 8);
    result.receipt_hash = text_column(stmt, 9);
    return result;
}

void validate_receipt_input(const VerificationReceiptInput& receipt) {
    require_text(receipt.receipt_id, "receipt_id");
    require_text(receipt.artifact_id, "artifact_id");
    require_text(receipt.verifier_id, "verifier_id");
    require_text(receipt.verifier_version, "verifier_version");
    require_text(receipt.artifact_sha256, "artifact_sha256");
    require_text(receipt.evidence_json, "evidence_json");
    if (!is_lower_hex(receipt.artifact_sha256, 64U)) {
        throw std::invalid_argument("artifact_sha256 must be 64 lowercase hexadecimal characters");
    }
}

} // namespace

std::string_view verification_verdict_name(VerificationVerdict verdict) noexcept {
    switch (verdict) {
        case VerificationVerdict::Verified: return "verified";
        case VerificationVerdict::Rejected: return "rejected";
    }
    return "rejected";
}

ArtifactRegistry::ArtifactRegistry(std::filesystem::path path)
    : path_(std::move(path)) {
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

ArtifactRegistry::~ArtifactRegistry() {
    if (db_) sqlite3_close(db_);
}

void ArtifactRegistry::initialize() {
    exec_sql(db_, R"SQL(
        CREATE TABLE IF NOT EXISTS artifact_registry_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            artifact_type TEXT NOT NULL,
            media_type TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
            locator TEXT NOT NULL,
            source_repository TEXT NOT NULL,
            source_commit TEXT NOT NULL,
            producer TEXT NOT NULL,
            producer_version TEXT NOT NULL,
            provenance_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_artifacts_digest
            ON artifacts(content_sha256);

        CREATE TABLE IF NOT EXISTS artifact_verification_receipts (
            sequence INTEGER PRIMARY KEY,
            receipt_id TEXT NOT NULL UNIQUE,
            artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
            verifier_id TEXT NOT NULL,
            verifier_version TEXT NOT NULL,
            verdict TEXT NOT NULL CHECK(verdict IN ('verified','rejected')),
            artifact_sha256 TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            previous_receipt_hash TEXT NOT NULL,
            receipt_hash TEXT NOT NULL UNIQUE,
            recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_artifact_receipts
            ON artifact_verification_receipts(artifact_id, sequence);

        CREATE TRIGGER IF NOT EXISTS artifacts_no_update
        BEFORE UPDATE ON artifacts
        BEGIN
            SELECT RAISE(ABORT, 'artifact records are append-only');
        END;

        CREATE TRIGGER IF NOT EXISTS artifacts_no_delete
        BEFORE DELETE ON artifacts
        BEGIN
            SELECT RAISE(ABORT, 'artifact records are append-only');
        END;

        CREATE TRIGGER IF NOT EXISTS artifact_receipts_no_update
        BEFORE UPDATE ON artifact_verification_receipts
        BEGIN
            SELECT RAISE(ABORT, 'verification receipts are append-only');
        END;

        CREATE TRIGGER IF NOT EXISTS artifact_receipts_no_delete
        BEFORE DELETE ON artifact_verification_receipts
        BEGIN
            SELECT RAISE(ABORT, 'verification receipts are append-only');
        END;
    )SQL");

    Statement query(db_, "SELECT value FROM artifact_registry_metadata WHERE key='schema_version';");
    const int rc = sqlite3_step(query.get());
    check(rc, db_, "read artifact registry schema");
    if (rc == SQLITE_DONE) {
        Statement insert(db_, "INSERT INTO artifact_registry_metadata(key,value) VALUES('schema_version','1');");
        check(sqlite3_step(insert.get()), db_, "insert artifact registry schema");
    } else if (text_column(query.get(), 0) != std::to_string(kSchemaVersion)) {
        throw std::runtime_error("unsupported artifact registry schema");
    }
}

void ArtifactRegistry::register_artifact(const ArtifactRecord& artifact) {
    validate_artifact(artifact);
    Statement insert(db_, R"SQL(
        INSERT INTO artifacts(
            artifact_id,artifact_type,media_type,content_sha256,size_bytes,
            locator,source_repository,source_commit,producer,producer_version,
            provenance_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?);
    )SQL");

    bind_text(db_, insert.get(), 1, artifact.artifact_id);
    bind_text(db_, insert.get(), 2, artifact.artifact_type);
    bind_text(db_, insert.get(), 3, artifact.media_type);
    bind_text(db_, insert.get(), 4, artifact.content_sha256);
    check(sqlite3_bind_int64(insert.get(), 5,
          static_cast<sqlite3_int64>(artifact.size_bytes)), db_, "bind artifact size");
    bind_text(db_, insert.get(), 6, artifact.locator);
    bind_text(db_, insert.get(), 7, artifact.source_repository);
    bind_text(db_, insert.get(), 8, artifact.source_commit);
    bind_text(db_, insert.get(), 9, artifact.producer);
    bind_text(db_, insert.get(), 10, artifact.producer_version);
    bind_text(db_, insert.get(), 11, artifact.provenance_json);
    check(sqlite3_step(insert.get()), db_, "register artifact");
}

VerificationReceipt ArtifactRegistry::append_verification(
    const VerificationReceiptInput& input) {
    validate_receipt_input(input);

    exec_sql(db_, "BEGIN IMMEDIATE;");
    try {
        {
            Statement artifact(db_, "SELECT content_sha256 FROM artifacts WHERE artifact_id=?;");
            bind_text(db_, artifact.get(), 1, input.artifact_id);
            const int rc = sqlite3_step(artifact.get());
            check(rc, db_, "lookup artifact for verification");
            if (rc == SQLITE_DONE) {
                throw std::invalid_argument("verification receipt references unknown artifact");
            }
            if (text_column(artifact.get(), 0) != input.artifact_sha256) {
                throw std::invalid_argument("verification receipt digest does not match registered artifact");
            }
        }

        long long sequence = 0;
        std::string previous_hash;
        {
            Statement last(db_, "SELECT sequence,receipt_hash FROM artifact_verification_receipts ORDER BY sequence DESC LIMIT 1;");
            const int rc = sqlite3_step(last.get());
            check(rc, db_, "read previous artifact verification receipt");
            if (rc == SQLITE_ROW) {
                sequence = sqlite3_column_int64(last.get(), 0) + 1;
                previous_hash = text_column(last.get(), 1);
            }
        }

        VerificationReceipt receipt;
        static_cast<VerificationReceiptInput&>(receipt) = input;
        receipt.sequence = sequence;
        receipt.previous_receipt_hash = previous_hash;
        receipt.receipt_hash = sha256_hex(receipt_hash_material(receipt));

        Statement insert(db_, R"SQL(
            INSERT INTO artifact_verification_receipts(
                sequence,receipt_id,artifact_id,verifier_id,verifier_version,
                verdict,artifact_sha256,evidence_json,previous_receipt_hash,receipt_hash
            ) VALUES(?,?,?,?,?,?,?,?,?,?);
        )SQL");
        check(sqlite3_bind_int64(insert.get(), 1, sequence), db_, "bind receipt sequence");
        bind_text(db_, insert.get(), 2, receipt.receipt_id);
        bind_text(db_, insert.get(), 3, receipt.artifact_id);
        bind_text(db_, insert.get(), 4, receipt.verifier_id);
        bind_text(db_, insert.get(), 5, receipt.verifier_version);
        bind_text(db_, insert.get(), 6, verdict_text(receipt.verdict));
        bind_text(db_, insert.get(), 7, receipt.artifact_sha256);
        bind_text(db_, insert.get(), 8, receipt.evidence_json);
        bind_text(db_, insert.get(), 9, receipt.previous_receipt_hash);
        bind_text(db_, insert.get(), 10, receipt.receipt_hash);
        check(sqlite3_step(insert.get()), db_, "append artifact verification receipt");

        exec_sql(db_, "COMMIT;");
        return receipt;
    } catch (...) {
        exec_sql(db_, "ROLLBACK;");
        throw;
    }
}

std::optional<ArtifactSnapshot> ArtifactRegistry::get(std::string_view artifact_id) const {
    if (artifact_id.empty()) throw std::invalid_argument("artifact_id must be non-empty");

    Statement query(db_, R"SQL(
        SELECT artifact_id,artifact_type,media_type,content_sha256,size_bytes,
               locator,source_repository,source_commit,producer,producer_version,
               provenance_json,created_at
        FROM artifacts WHERE artifact_id=?;
    )SQL");
    bind_text(db_, query.get(), 1, artifact_id);
    const int rc = sqlite3_step(query.get());
    check(rc, db_, "get artifact");
    if (rc == SQLITE_DONE) return std::nullopt;

    ArtifactSnapshot snapshot;
    auto& a = snapshot.artifact;
    a.artifact_id = text_column(query.get(), 0);
    a.artifact_type = text_column(query.get(), 1);
    a.media_type = text_column(query.get(), 2);
    a.content_sha256 = text_column(query.get(), 3);
    a.size_bytes = static_cast<std::uint64_t>(sqlite3_column_int64(query.get(), 4));
    a.locator = text_column(query.get(), 5);
    a.source_repository = text_column(query.get(), 6);
    a.source_commit = text_column(query.get(), 7);
    a.producer = text_column(query.get(), 8);
    a.producer_version = text_column(query.get(), 9);
    a.provenance_json = text_column(query.get(), 10);
    a.created_at = text_column(query.get(), 11);

    Statement latest(db_, R"SQL(
        SELECT sequence,receipt_id,artifact_id,verifier_id,verifier_version,
               verdict,artifact_sha256,evidence_json,previous_receipt_hash,receipt_hash
        FROM artifact_verification_receipts
        WHERE artifact_id=? ORDER BY sequence DESC LIMIT 1;
    )SQL");
    bind_text(db_, latest.get(), 1, artifact_id);
    const int latest_rc = sqlite3_step(latest.get());
    check(latest_rc, db_, "get latest artifact verification receipt");
    if (latest_rc == SQLITE_ROW) snapshot.latest_verification = row_to_receipt(latest.get());
    return snapshot;
}

std::vector<ArtifactSnapshot> ArtifactRegistry::list(
    std::size_t limit,
    std::size_t offset) const {
    if (limit == 0U || limit > 500U) {
        throw std::invalid_argument("artifact list limit must be in 1..500");
    }
    if (offset > static_cast<std::size_t>(std::numeric_limits<sqlite3_int64>::max())) {
        throw std::invalid_argument("artifact list offset exceeds SQLite integer range");
    }

    Statement query(db_, "SELECT artifact_id FROM artifacts ORDER BY created_at DESC, artifact_id ASC LIMIT ? OFFSET ?;");
    check(sqlite3_bind_int64(query.get(), 1, static_cast<sqlite3_int64>(limit)), db_, "bind artifact list limit");
    check(sqlite3_bind_int64(query.get(), 2, static_cast<sqlite3_int64>(offset)), db_, "bind artifact list offset");

    std::vector<std::string> ids;
    while (true) {
        const int rc = sqlite3_step(query.get());
        check(rc, db_, "list artifact IDs");
        if (rc == SQLITE_DONE) break;
        ids.push_back(text_column(query.get(), 0));
    }

    std::vector<ArtifactSnapshot> result;
    result.reserve(ids.size());
    for (const auto& id : ids) {
        auto snapshot = get(id);
        if (snapshot.has_value()) result.push_back(std::move(*snapshot));
    }
    return result;
}

std::vector<VerificationReceipt> ArtifactRegistry::verification_receipts(
    std::string_view artifact_id) const {
    if (artifact_id.empty()) throw std::invalid_argument("artifact_id must be non-empty");

    Statement query(db_, R"SQL(
        SELECT sequence,receipt_id,artifact_id,verifier_id,verifier_version,
               verdict,artifact_sha256,evidence_json,previous_receipt_hash,receipt_hash
        FROM artifact_verification_receipts
        WHERE artifact_id=? ORDER BY sequence;
    )SQL");
    bind_text(db_, query.get(), 1, artifact_id);

    std::vector<VerificationReceipt> result;
    while (true) {
        const int rc = sqlite3_step(query.get());
        check(rc, db_, "list artifact verification receipts");
        if (rc == SQLITE_DONE) break;
        result.push_back(row_to_receipt(query.get()));
    }
    return result;
}

ArtifactRegistryVerification ArtifactRegistry::verify_receipt_chain() const {
    ArtifactRegistryVerification result;
    std::string expected_previous;

    Statement query(db_, R"SQL(
        SELECT r.sequence,r.receipt_id,r.artifact_id,r.verifier_id,r.verifier_version,
               r.verdict,r.artifact_sha256,r.evidence_json,r.previous_receipt_hash,
               r.receipt_hash,a.content_sha256
        FROM artifact_verification_receipts r
        JOIN artifacts a ON a.artifact_id=r.artifact_id
        ORDER BY r.sequence;
    )SQL");

    while (true) {
        const int rc = sqlite3_step(query.get());
        check(rc, db_, "verify artifact receipt chain");
        if (rc == SQLITE_DONE) break;

        const auto receipt = row_to_receipt(query.get());
        result.receipt_count += 1;
        if (receipt.sequence != result.receipt_count - 1) {
            result.valid = false;
            result.first_invalid_sequence = receipt.sequence;
            result.reason = "non-contiguous receipt sequence";
            return result;
        }
        if (receipt.previous_receipt_hash != expected_previous) {
            result.valid = false;
            result.first_invalid_sequence = receipt.sequence;
            result.reason = "previous receipt hash mismatch";
            return result;
        }
        if (receipt.artifact_sha256 != text_column(query.get(), 10)) {
            result.valid = false;
            result.first_invalid_sequence = receipt.sequence;
            result.reason = "receipt digest no longer matches registered artifact";
            return result;
        }
        const auto recomputed = sha256_hex(receipt_hash_material(receipt));
        if (recomputed != receipt.receipt_hash) {
            result.valid = false;
            result.first_invalid_sequence = receipt.sequence;
            result.reason = "receipt hash mismatch";
            return result;
        }
        expected_previous = receipt.receipt_hash;
    }

    result.root_hash = expected_previous;
    return result;
}

} // namespace expert_robot::artifacts
