#include "expert_robot/model_server.hpp"

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#ifndef _WIN32
#include <arpa/inet.h>
#include <csignal>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace expert_robot {
namespace {

#ifndef _WIN32
bool port_accepting(
    const std::string& host,
    int port) {
    const int fd = socket(
        AF_INET,
        SOCK_STREAM,
        0);
    if (fd < 0) return false;

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port =
        htons(static_cast<std::uint16_t>(port));

    if (inet_pton(
            AF_INET,
            host.c_str(),
            &addr.sin_addr) != 1) {
        close(fd);
        return false;
    }

    const bool ok =
        connect(
            fd,
            reinterpret_cast<sockaddr*>(&addr),
            sizeof(addr)) == 0;
    close(fd);
    return ok;
}
#endif

} // namespace

void validate_llama_server_config(
    const LlamaServerConfig& c) {
    if (c.executable.empty()) {
        throw std::invalid_argument(
            "llama-server executable must be non-empty");
    }
    if (c.model_path.empty()) {
        throw std::invalid_argument(
            "llama-server model_path must be non-empty");
    }
    if (c.host != "127.0.0.1") {
        throw std::invalid_argument(
            "llama-server host must be exactly 127.0.0.1");
    }
    if (c.port <= 0 || c.port > 65535) {
        throw std::invalid_argument(
            "llama-server port must be in 1..65535");
    }
    if (c.parallel_slots <= 0) {
        throw std::invalid_argument(
            "llama-server parallel_slots must be positive");
    }
    if (c.context_size <= 0) {
        throw std::invalid_argument(
            "llama-server context_size must be positive");
    }
    if (c.startup_timeout_seconds <= 0) {
        throw std::invalid_argument(
            "llama-server startup timeout must be positive");
    }
}

LlamaServerProcess::LlamaServerProcess(
    LlamaServerConfig config)
    : config_(std::move(config)) {
    validate_llama_server_config(config_);
}

LlamaServerProcess::~LlamaServerProcess() {
    stop();
}

const LlamaServerConfig&
LlamaServerProcess::config() const noexcept {
    return config_;
}

std::string LlamaServerProcess::server_base() const {
    return "http://" +
           config_.host +
           ":" +
           std::to_string(config_.port);
}

bool LlamaServerProcess::running() const noexcept {
#ifdef _WIN32
    return false;
#else
    if (pid_ <= 0) return false;

    int status = 0;
    const pid_t result =
        waitpid(
            static_cast<pid_t>(pid_),
            &status,
            WNOHANG);
    return result == 0;
#endif
}

void LlamaServerProcess::start() {
    if (running()) return;

#ifdef _WIN32
    throw std::runtime_error(
        "LlamaServerProcess is not implemented on Windows yet");
#else
    if (port_accepting(
            config_.host,
            config_.port)) {
        throw std::runtime_error(
            "configured llama-server port is already in use");
    }

    const auto temp_dir =
        std::filesystem::temp_directory_path();
    log_path_ =
        temp_dir /
        ("expert-robot-llama-server-" +
         std::to_string(config_.port) +
         ".log");

    std::vector<std::string> args = {
        config_.executable.string(),
        "-m",
        std::filesystem::absolute(
            config_.model_path).string(),
        "--host",
        config_.host,
        "--port",
        std::to_string(config_.port),
        "--parallel",
        std::to_string(config_.parallel_slots),
        "--ctx-size",
        std::to_string(config_.context_size),
        "--cont-batching",
        "--no-ui-mcp-proxy",
    };

    if (config_.offline) {
        args.push_back("--offline");
    }

    std::vector<char*> argv;
    argv.reserve(args.size() + 1U);
    for (auto& arg : args) {
        argv.push_back(arg.data());
    }
    argv.push_back(nullptr);

    const pid_t child = fork();
    if (child < 0) {
        throw std::runtime_error(
            "fork failed for llama-server");
    }

    if (child == 0) {
        const int fd = open(
            log_path_.c_str(),
            O_WRONLY | O_CREAT | O_TRUNC,
            0600);
        if (fd < 0) _exit(126);

        dup2(fd, STDOUT_FILENO);
        dup2(fd, STDERR_FILENO);
        close(fd);

        execvp(
            argv[0],
            argv.data());
        _exit(127);
    }

    pid_ = static_cast<long long>(child);

    const auto deadline =
        std::chrono::steady_clock::now() +
        std::chrono::seconds(
            config_.startup_timeout_seconds);

    while (
        std::chrono::steady_clock::now() <
        deadline) {
        if (port_accepting(
                config_.host,
                config_.port)) {
            return;
        }

        int status = 0;
        const pid_t result =
            waitpid(
                child,
                &status,
                WNOHANG);
        if (result == child) {
            pid_ = -1;
            std::ifstream in(
                log_path_,
                std::ios::binary);
            std::string log(
                (std::istreambuf_iterator<char>(in)),
                std::istreambuf_iterator<char>());
            throw std::runtime_error(
                "llama-server exited during startup: " +
                log.substr(
                    log.size() > 4096U
                        ? log.size() - 4096U
                        : 0U));
        }

        std::this_thread::sleep_for(
            std::chrono::milliseconds(50));
    }

    stop();
    throw std::runtime_error(
        "llama-server startup timed out");
#endif
}

void LlamaServerProcess::stop() noexcept {
#ifndef _WIN32
    if (pid_ <= 0) return;

    const pid_t child =
        static_cast<pid_t>(pid_);

    kill(child, SIGTERM);

    const auto deadline =
        std::chrono::steady_clock::now() +
        std::chrono::seconds(3);

    int status = 0;
    while (
        std::chrono::steady_clock::now() <
        deadline) {
        const pid_t result =
            waitpid(
                child,
                &status,
                WNOHANG);
        if (result == child || result < 0) {
            pid_ = -1;
            return;
        }
        std::this_thread::sleep_for(
            std::chrono::milliseconds(25));
    }

    kill(child, SIGKILL);
    waitpid(
        child,
        &status,
        0);
    pid_ = -1;
#else
    pid_ = -1;
#endif
}

} // namespace expert_robot
