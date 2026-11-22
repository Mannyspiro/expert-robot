#include "expert_robot/runtime.hpp"

#include "expert_robot/json_util.hpp"

#include <cstdint>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>

namespace expert_robot {
namespace {

bool extract_json_string(const std::string& line, const std::string& key, std::string& out) {
    const std::string needle = "\"" + key + "\"";
    const auto key_pos = line.find(needle);
    if (key_pos == std::string::npos) return false;
    const auto colon = line.find(':', key_pos + needle.size());
    if (colon == std::string::npos) return false;
    auto pos = line.find('"', colon + 1);
    if (pos == std::string::npos) return false;
    ++pos;

    std::ostringstream value;
    bool escaped = false;
    for (; pos < line.size(); ++pos) {
        const char ch = line[pos];
        if (escaped) {
            switch (ch) {
                case 'n': value << '\n'; break;
                case 'r': value << '\r'; break;
                case 't': value << '\t'; break;
                case '"': value << '"'; break;
                case '\\': value << '\\'; break;
                default: value << ch; break;
            }
            escaped = false;
            continue;
        }
        if (ch == '\\') {
            escaped = true;
            continue;
        }
        if (ch == '"') {
            out = value.str();
            return true;
        }
        value << ch;
    }
    return false;
}

std::string required_string(const std::string& object, std::string_view key) {
    const auto value = json_util::string_field(object, key);
    if (value.empty()) throw std::invalid_argument("missing or empty payload field: " + std::string(key));
    return value;
}

std::string quote_json(std::string_view value) {
    return "\"" + json_util::escape(value) + "\"";
}

std::string receipt_json(const artifacts::VerificationReceipt& receipt) {
    std::ostringstream out;
    out << "{"
        << "\"sequence\":" << receipt.sequence << ","
        << "\"receipt_id\":" << quote_json(receipt.receipt_id) << ","
        << "\"artifact_id\":" << quote_json(receipt.artifact_id) << ","
        << "\"verifier_id\":" << quote_json(receipt.verifier_id) << ","
        << "\"verifier_version\":" << quote_json(receipt.verifier_version) << ","
        << "\"verdict\":" << quote_json(artifacts::verification_verdict_name(receipt.verdict)) << ","
        << "\"artifact_sha256\":" << quote_json(receipt.artifact_sha256) << ","
        << "\"evidence_json\":" << quote_json(receipt.evidence_json) << ","
        << "\"previous_receipt_hash\":" << quote_json(receipt.previous_receipt_hash) << ","
        << "\"receipt_hash\":" << quote_json(receipt.receipt_hash)
        << "}";
    return out.str();
}

std::string artifact_json(const artifacts::ArtifactSnapshot& snapshot) {
    const auto& artifact = snapshot.artifact;
    std::ostringstream out;
    out << "{"
        << "\"artifact_id\":" << quote_json(artifact.artifact_id) << ","
        << "\"artifact_type\":" << quote_json(artifact.artifact_type) << ","
        << "\"media_type\":" << quote_json(artifact.media_type) << ","
        << "\"content_sha256\":" << quote_json(artifact.content_sha256) << ","
        << "\"size_bytes\":" << artifact.size_bytes << ","
        << "\"locator\":" << quote_json(artifact.locator) << ","
        << "\"source_repository\":" << quote_json(artifact.source_repository) << ","
        << "\"source_commit\":" << quote_json(artifact.source_commit) << ","
        << "\"producer\":" << quote_json(artifact.producer) << ","
        << "\"producer_version\":" << quote_json(artifact.producer_version) << ","
        << "\"provenance_json\":" << quote_json(artifact.provenance_json) << ","
        << "\"created_at\":" << quote_json(artifact.created_at) << ","
        << "\"latest_verification\":";
    if (snapshot.latest_verification.has_value()) {
        out << receipt_json(*snapshot.latest_verification);
    } else {
        out << "null";
    }
    out << "}";
    return out.str();
}

artifacts::VerificationVerdict parse_verdict(std::string_view value) {
    if (value == "verified") return artifacts::VerificationVerdict::Verified;
    if (value == "rejected") return artifacts::VerificationVerdict::Rejected;
    throw std::invalid_argument("verdict must be 'verified' or 'rejected'");
}

std::uint64_t parse_unsigned_field(const std::string& payload, std::string_view key, std::string fallback = "0") {
    const auto value = json_util::string_field(payload, key, fallback);
    std::size_t consumed = 0;
    const auto parsed = std::stoull(value, &consumed);
    if (consumed != value.size()) throw std::invalid_argument("size_bytes must be an unsigned integer string");
    return static_cast<std::uint64_t>(parsed);
}

} // namespace

std::string json_escape(const std::string& value) {
    return json_util::escape(value);
}

bool parse_request_line(const std::string& line, Request& out, std::string& error) {
    if (!extract_json_string(line, "id", out.id)) {
        error = "missing string field: id";
        return false;
    }
    if (!extract_json_string(line, "role", out.role)) {
        error = "missing string field: role";
        return false;
    }
    if (!extract_json_string(line, "task", out.task)) {
        error = "missing string field: task";
        return false;
    }
    if (line.find("\"payload\"") != std::string::npos &&
        !extract_json_string(line, "payload", out.payload)) {
        error = "payload must be a valid JSON string";
        return false;
    }
    return true;
}

std::string serialize_response(const Response& response) {
    std::ostringstream out;
    out << "{"
        << "\"id\":\"" << json_escape(response.id) << "\","
        << "\"ok\":" << (response.ok ? "true" : "false") << ","
        << "\"result\":\"" << json_escape(response.result) << "\","
        << "\"error\":\"" << json_escape(response.error) << "\""
        << "}";
    return out.str();
}

Runtime::Runtime(std::filesystem::path artifact_registry_path)
    : artifact_registry_(std::move(artifact_registry_path)) {}

Response Runtime::handle(const Request& request) {
    Response response;
    response.id = request.id;

    if (request.role.empty()) {
        response.error = "role must not be empty";
        return response;
    }
    if (request.task.empty()) {
        response.error = "task must not be empty";
        return response;
    }

    if (request.role == "health") {
        response.ok = true;
        response.result = "runtime protocol healthy";
        return response;
    }

    if (request.role == "artifact") {
        try {
            if (request.task == "register") {
                artifacts::ArtifactRecord artifact;
                artifact.artifact_id = required_string(request.payload, "artifact_id");
                artifact.artifact_type = required_string(request.payload, "artifact_type");
                artifact.media_type = required_string(request.payload, "media_type");
                artifact.content_sha256 = required_string(request.payload, "content_sha256");
                artifact.size_bytes = parse_unsigned_field(request.payload, "size_bytes");
                artifact.locator = required_string(request.payload, "locator");
                artifact.source_repository = json_util::string_field(request.payload, "source_repository");
                artifact.source_commit = json_util::string_field(request.payload, "source_commit");
                artifact.producer = required_string(request.payload, "producer");
                artifact.producer_version = required_string(request.payload, "producer_version");
                artifact.provenance_json = required_string(request.payload, "provenance_json");
                artifact_registry_.register_artifact(artifact);
                response.ok = true;
                response.result = "{\"artifact_id\":" + quote_json(artifact.artifact_id) +
                    ",\"content_sha256\":" + quote_json(artifact.content_sha256) + "}";
                return response;
            }

            if (request.task == "list") {
                const auto limit = parse_unsigned_field(request.payload, "limit", "50");
                const auto offset = parse_unsigned_field(request.payload, "offset", "0");
                if (limit > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max()) ||
                    offset > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
                    throw std::invalid_argument("artifact list pagination value is too large");
                }
                const auto artifacts = artifact_registry_.list(
                    static_cast<std::size_t>(limit), static_cast<std::size_t>(offset));
                std::ostringstream out;
                out << "[";
                for (std::size_t i = 0; i < artifacts.size(); ++i) {
                    if (i != 0U) out << ",";
                    out << artifact_json(artifacts[i]);
                }
                out << "]";
                response.ok = true;
                response.result = out.str();
                return response;
            }

            if (request.task == "get") {
                const auto artifact_id = required_string(request.payload, "artifact_id");
                const auto snapshot = artifact_registry_.get(artifact_id);
                if (!snapshot.has_value()) throw std::out_of_range("artifact not found");
                response.ok = true;
                response.result = artifact_json(*snapshot);
                return response;
            }

            if (request.task == "record_receipt") {
                artifacts::VerificationReceiptInput receipt;
                receipt.receipt_id = required_string(request.payload, "receipt_id");
                receipt.artifact_id = required_string(request.payload, "artifact_id");
                receipt.verifier_id = required_string(request.payload, "verifier_id");
                receipt.verifier_version = required_string(request.payload, "verifier_version");
                receipt.verdict = parse_verdict(required_string(request.payload, "verdict"));
                receipt.artifact_sha256 = required_string(request.payload, "artifact_sha256");
                receipt.evidence_json = required_string(request.payload, "evidence_json");
                const auto stored = artifact_registry_.append_verification(receipt);
                response.ok = true;
                response.result = receipt_json(stored);
                return response;
            }

            if (request.task == "receipts") {
                const auto artifact_id = required_string(request.payload, "artifact_id");
                const auto receipts = artifact_registry_.verification_receipts(artifact_id);
                std::ostringstream out;
                out << "[";
                for (std::size_t i = 0; i < receipts.size(); ++i) {
                    if (i != 0U) out << ",";
                    out << receipt_json(receipts[i]);
                }
                out << "]";
                response.ok = true;
                response.result = out.str();
                return response;
            }

            if (request.task == "verify_chain") {
                const auto verification = artifact_registry_.verify_receipt_chain();
                std::ostringstream out;
                out << "{"
                    << "\"valid\":" << (verification.valid ? "true" : "false") << ","
                    << "\"receipt_count\":" << verification.receipt_count << ","
                    << "\"first_invalid_sequence\":" << verification.first_invalid_sequence << ","
                    << "\"reason\":" << quote_json(verification.reason) << ","
                    << "\"root_hash\":" << quote_json(verification.root_hash)
                    << "}";
                response.ok = true;
                response.result = out.str();
                return response;
            }

            throw std::invalid_argument("unknown artifact operation");
        } catch (const std::exception& error) {
            response.ok = false;
            response.error = error.what();
            return response;
        }
    }

    response.ok = false;
    response.error =
        "generic protocol runtime does not own model state; "
        "use expert_robot_research for bounded offline math research";
    return response;
}

} // namespace expert_robot
