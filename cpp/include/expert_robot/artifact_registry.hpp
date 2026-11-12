#pragma once

#include <cstdint>
#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

struct sqlite3;

namespace expert_robot::artifacts {

enum class VerificationVerdict {
    Verified,
    Rejected,
};

[[nodiscard]] std::string_view verification_verdict_name(
    VerificationVerdict verdict) noexcept;

struct ArtifactRecord {
    std::string artifact_id;
    std::string artifact_type;
    std::string media_type;
    std::string content_sha256;
    std::uint64_t size_bytes{0};
    std::string locator;
    std::string source_repository;
    std::string source_commit;
    std::string producer;
    std::string producer_version;
    std::string provenance_json;
    std::string created_at;
};

struct VerificationReceiptInput {
    std::string receipt_id;
    std::string artifact_id;
    std::string verifier_id;
    std::string verifier_version;
    VerificationVerdict verdict{VerificationVerdict::Rejected};
    std::string artifact_sha256;
    std::string evidence_json;
};

struct VerificationReceipt : VerificationReceiptInput {
    long long sequence{0};
    std::string previous_receipt_hash;
    std::string receipt_hash;
};

struct ArtifactSnapshot {
    ArtifactRecord artifact;
    std::optional<VerificationReceipt> latest_verification;
};

struct ArtifactRegistryVerification {
    bool valid{true};
    long long receipt_count{0};
    long long first_invalid_sequence{-1};
    std::string reason;
    std::string root_hash;
};

// The registry stores metadata and content digests, never artifact bytes.
// Registration and verification are append-only. A verification receipt is
// accepted only when it names the exact digest already registered for the
// artifact; it cannot mutate the artifact record.
class ArtifactRegistry {
public:
    explicit ArtifactRegistry(std::filesystem::path path);
    ~ArtifactRegistry();

    ArtifactRegistry(const ArtifactRegistry&) = delete;
    ArtifactRegistry& operator=(const ArtifactRegistry&) = delete;

    void register_artifact(const ArtifactRecord& artifact);

    [[nodiscard]] VerificationReceipt append_verification(
        const VerificationReceiptInput& receipt);

    [[nodiscard]] std::optional<ArtifactSnapshot> get(
        std::string_view artifact_id) const;

    [[nodiscard]] std::vector<VerificationReceipt> verification_receipts(
        std::string_view artifact_id) const;

    [[nodiscard]] ArtifactRegistryVerification verify_receipt_chain() const;

private:
    void initialize();

    std::filesystem::path path_;
    sqlite3* db_{nullptr};
};

} // namespace expert_robot::artifacts
