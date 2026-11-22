#include "expert_robot/artifact_registry.hpp"
#include "expert_robot/sha256.hpp"

#include <sqlite3.h>

#include <cassert>
#include <filesystem>
#include <stdexcept>
#include <string>

int main() {
    using namespace expert_robot;
    using namespace expert_robot::artifacts;

    const auto db = std::filesystem::temp_directory_path() /
        "expert-robot-artifact-registry-smoke.sqlite3";
    std::filesystem::remove(db);

    const std::string bytes = "{\"answer\":42}\n";
    const std::string digest = sha256_hex(bytes);
    const std::string commit(40, 'a');

    {
        ArtifactRegistry registry(db);
        ArtifactRecord artifact{
            .artifact_id = "artifact-0001",
            .artifact_type = "research.result",
            .media_type = "application/json",
            .content_sha256 = digest,
            .size_bytes = static_cast<std::uint64_t>(bytes.size()),
            .locator = "artifact-store://research/episode-001/result.json",
            .source_repository = "Mannyspiro/expert-robot",
            .source_commit = commit,
            .producer = "merlin.math-research",
            .producer_version = "0.1.0",
            .provenance_json = "{\"episode_id\":\"episode-001\",\"source\":\"lean\"}",
        };
        registry.register_artifact(artifact);

        const auto initial = registry.get(artifact.artifact_id);
        assert(initial.has_value());
        assert(initial->artifact.content_sha256 == digest);
        assert(initial->artifact.source_commit == commit);
        assert(!initial->latest_verification.has_value());

        VerificationReceiptInput verified{
            .receipt_id = "receipt-0001",
            .artifact_id = artifact.artifact_id,
            .verifier_id = "cace",
            .verifier_version = "1.0.0",
            .verdict = VerificationVerdict::Verified,
            .artifact_sha256 = digest,
            .evidence_json = "{\"digest_match\":true,\"independent\":true}",
        };
        const auto first = registry.append_verification(verified);
        assert(first.sequence == 0);
        assert(first.previous_receipt_hash.empty());
        assert(!first.receipt_hash.empty());

        const auto after_first = registry.get(artifact.artifact_id);
        assert(after_first.has_value());
        assert(after_first->latest_verification.has_value());
        assert(after_first->latest_verification->verdict == VerificationVerdict::Verified);

        auto rejected = verified;
        rejected.receipt_id = "receipt-0002";
        rejected.verifier_id = "cace.held-out-auditor";
        rejected.verdict = VerificationVerdict::Rejected;
        rejected.evidence_json = "{\"independent_check\":false}";
        const auto second = registry.append_verification(rejected);
        assert(second.sequence == 1);
        assert(second.previous_receipt_hash == first.receipt_hash);

        const auto receipts = registry.verification_receipts(artifact.artifact_id);
        assert(receipts.size() == 2);
        assert(receipts[0].verdict == VerificationVerdict::Verified);
        assert(receipts[1].verdict == VerificationVerdict::Rejected);

        const auto latest = registry.get(artifact.artifact_id);
        assert(latest.has_value());
        assert(latest->latest_verification->verdict == VerificationVerdict::Rejected);

        const auto chain = registry.verify_receipt_chain();
        assert(chain.valid);
        assert(chain.receipt_count == 2);
        assert(chain.root_hash == second.receipt_hash);

        auto mismatched = verified;
        mismatched.receipt_id = "receipt-bad-digest";
        mismatched.artifact_sha256 = sha256_hex("different bytes");
        bool mismatch_rejected = false;
        try {
            (void)registry.append_verification(mismatched);
        } catch (const std::invalid_argument&) {
            mismatch_rejected = true;
        }
        assert(mismatch_rejected);

        bool duplicate_rejected = false;
        try {
            registry.register_artifact(artifact);
        } catch (const std::exception&) {
            duplicate_rejected = true;
        }
        assert(duplicate_rejected);

        bool invalid_digest_rejected = false;
        try {
            auto invalid = artifact;
            invalid.artifact_id = "artifact-invalid";
            invalid.content_sha256 = "not-a-digest";
            registry.register_artifact(invalid);
        } catch (const std::invalid_argument&) {
            invalid_digest_rejected = true;
        }
        assert(invalid_digest_rejected);

        sqlite3* raw = nullptr;
        assert(sqlite3_open(db.string().c_str(), &raw) == SQLITE_OK);
        char* error = nullptr;
        const int update_rc = sqlite3_exec(
            raw, "UPDATE artifacts SET locator='changed' WHERE artifact_id='artifact-0001';",
            nullptr, nullptr, &error);
        if (error) sqlite3_free(error);
        assert(update_rc != SQLITE_OK);

        error = nullptr;
        const int delete_rc = sqlite3_exec(
            raw, "DELETE FROM artifact_verification_receipts WHERE receipt_id='receipt-0001';",
            nullptr, nullptr, &error);
        if (error) sqlite3_free(error);
        assert(delete_rc != SQLITE_OK);
        sqlite3_close(raw);

        const auto final_chain = registry.verify_receipt_chain();
        assert(final_chain.valid);
        assert(final_chain.receipt_count == 2);
    }

    std::filesystem::remove(db);
    return 0;
}
