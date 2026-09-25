#pragma once

#include <filesystem>
#include <string>

namespace expert_robot {

struct LlamaServerConfig {
    std::filesystem::path executable{"llama-server"};
    std::filesystem::path model_path;

    std::string host{"127.0.0.1"};
    int port{8081};
    int parallel_slots{2};
    int context_size{8192};
    int startup_timeout_seconds{120};

    bool offline{true};
};

void validate_llama_server_config(
    const LlamaServerConfig& config);

/**
 * Owns one persistent local llama-server subprocess.
 *
 * The server is always bound to loopback, never enables llama.cpp agent/tools
 * or MCP features, and may be shared by many lightweight llama-cli workers.
 */
class LlamaServerProcess {
public:
    explicit LlamaServerProcess(
        LlamaServerConfig config);
    ~LlamaServerProcess();

    LlamaServerProcess(
        const LlamaServerProcess&) = delete;
    LlamaServerProcess& operator=(
        const LlamaServerProcess&) = delete;

    void start();
    void stop() noexcept;

    [[nodiscard]] bool running() const noexcept;
    [[nodiscard]] std::string server_base() const;
    [[nodiscard]] const LlamaServerConfig& config() const noexcept;

private:
    LlamaServerConfig config_;
    long long pid_{-1};
    std::filesystem::path log_path_;
};

} // namespace expert_robot
