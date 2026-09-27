#pragma once

#include <filesystem>
#include <string>
#include <string_view>

namespace expert_robot {

struct TextGenerationRequest {
    std::string system_prompt;
    std::string user_prompt;
};

struct TextGenerationResult {
    bool ok{false};
    int exit_code{1};
    bool timed_out{false};
    std::string output;
    std::string diagnostics;
};

class ITextGenerationBackend {
public:
    virtual ~ITextGenerationBackend() = default;

    [[nodiscard]] virtual TextGenerationResult generate(
        const TextGenerationRequest& request) = 0;

    // Direct model-loading backends are serialized by default. Backends backed
    // by a persistent model server may override this so the supervisor can
    // issue concurrent requests and let the server batch/queue them safely.
    [[nodiscard]] virtual bool supports_concurrent_requests() const noexcept {
        return false;
    }
};

struct LlamaCliConfig {
    std::filesystem::path executable{"llama-cli"};
    std::filesystem::path model_path;
    std::filesystem::path json_schema_path;

    // Optional persistent local llama-server. When set, llama-cli connects to
    // this endpoint and does not reload model weights for every agent call.
    // Only loopback HTTP endpoints are accepted.
    std::string server_base;
    std::string chat_template;

    int max_tokens{1024};
    double temperature{0.15};
    double top_p{0.90};
    int seed{1};
    int timeout_seconds{180};

    std::size_t max_output_bytes{262144};
    std::size_t max_diagnostic_bytes{32768};
};

void validate_llama_cli_config(const LlamaCliConfig& config);

/**
 * Local llama.cpp subprocess backend.
 *
 * Security properties:
 * - no shell invocation
 * - argv constructed directly
 * - prompt/system text passed through private files rather than shell arguments
 * - bounded execution time
 * - bounded output read
 * - JSON schema supplied to llama.cpp
 * - temp files removed after every call
 */
class LlamaCliBackend final : public ITextGenerationBackend {
public:
    explicit LlamaCliBackend(LlamaCliConfig config);

    [[nodiscard]] const LlamaCliConfig& config() const noexcept;

    [[nodiscard]] TextGenerationResult generate(
        const TextGenerationRequest& request) override;

    [[nodiscard]] bool supports_concurrent_requests() const noexcept override;

private:
    LlamaCliConfig config_;
};

} // namespace expert_robot
