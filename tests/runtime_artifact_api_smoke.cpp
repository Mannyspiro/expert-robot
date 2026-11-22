#include "expert_robot/json_util.hpp"
#include "expert_robot/runtime.hpp"
#include "expert_robot/sha256.hpp"

#include <cassert>
#include <filesystem>
#include <string>

int main() {
    using namespace expert_robot;

    const auto db = std::filesystem::temp_directory_path() /
        "expert-robot-runtime-artifact-api.sqlite3";
    std::filesystem::remove(db);

    {
        Runtime runtime(db);
        const std::string content_digest = sha256_hex("artifact bytes");
        const std::string artifact_payload =
            "{\"artifact_id\":\"runtime-artifact-1\","
            "\"artifact_type\":\"research.result\","
            "\"media_type\":\"application/json\","
            "\"content_sha256\":\"" + content_digest + "\","
            "\"size_bytes\":\"14\","
            "\"locator\":\"artifact-store://runtime/1\","
            "\"source_repository\":\"Mannyspiro/expert-robot\","
            "\"source_commit\":\"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\","
            "\"producer\":\"merlin.runtime\","
            "\"producer_version\":\"0.1.0\","
            "\"provenance_json\":\"{\\\"episode_id\\\":\\\"ep-1\\\"}\"}";

        const std::string request_line =
            "{\"id\":\"register-1\",\"role\":\"artifact\",\"task\":\"register\",\"payload\":\"" +
            json_util::escape(artifact_payload) + "\"}";

        Request request;
        std::string error;
        assert(parse_request_line(request_line, request, error));
        assert(request.payload == artifact_payload);
        const auto registered = runtime.handle(request);
        assert(registered.ok);
        assert(registered.result.find("runtime-artifact-1") != std::string::npos);

        Request get;
        get.id = "get-1";
        get.role = "artifact";
        get.task = "get";
        get.payload = "{\"artifact_id\":\"runtime-artifact-1\"}";
        const auto fetched = runtime.handle(get);
        assert(fetched.ok);
        assert(fetched.result.find(content_digest) != std::string::npos);

        Request list;
        list.id = "list-1";
        list.role = "artifact";
        list.task = "list";
        list.payload = R"JSON({"limit":"10","offset":"0"})JSON";
        const auto listed = runtime.handle(list);
        assert(listed.ok);
        assert(listed.result.find("runtime-artifact-1") != std::string::npos);

        Request verify;
        verify.id = "verify-1";
        verify.role = "artifact";
        verify.task = "record_receipt";
        verify.payload =
            "{\"receipt_id\":\"runtime-receipt-1\","
            "\"artifact_id\":\"runtime-artifact-1\","
            "\"verifier_id\":\"cace\","
            "\"verifier_version\":\"1.0.0\","
            "\"verdict\":\"verified\","
            "\"artifact_sha256\":\"" + content_digest + "\","
            "\"evidence_json\":\"{\\\"independent\\\":true}\"}";
        const auto receipt = runtime.handle(verify);
        assert(receipt.ok);
        assert(receipt.result.find("runtime-receipt-1") != std::string::npos);

        Request chain;
        chain.id = "chain-1";
        chain.role = "artifact";
        chain.task = "verify_chain";
        const auto chain_result = runtime.handle(chain);
        assert(chain_result.ok);
        assert(chain_result.result.find("\"valid\":true") != std::string::npos);
        assert(chain_result.result.find("\"receipt_count\":1") != std::string::npos);

        Request bad;
        bad.id = "bad-1";
        bad.role = "artifact";
        bad.task = "record_receipt";
        bad.payload =
            "{\"receipt_id\":\"bad-receipt\","
            "\"artifact_id\":\"runtime-artifact-1\","
            "\"verifier_id\":\"cace\","
            "\"verifier_version\":\"1.0.0\","
            "\"verdict\":\"verified\","
            "\"artifact_sha256\":\"" + sha256_hex("wrong") + "\","
            "\"evidence_json\":\"{}\"}";
        const auto rejected = runtime.handle(bad);
        assert(!rejected.ok);
        assert(rejected.error.find("digest does not match") != std::string::npos);
    }

    std::filesystem::remove(db);
    return 0;
}
