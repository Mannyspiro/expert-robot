#include "expert_robot/text_generation.hpp"

#include <atomic>
#include <chrono>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#ifndef _WIN32
#include <csignal>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace expert_robot {
namespace {

std::string unique_suffix() {
    static std::atomic<unsigned long long> counter{0};
    const auto ticks =
        std::chrono::steady_clock::now().time_since_epoch().count();
    return std::to_string(ticks) + "-" +
           std::to_string(counter.fetch_add(1));
}

void write_private_file(
    const std::filesystem::path& path,
    std::string_view content) {
    {
        std::ofstream out(
            path,
            std::ios::binary | std::ios::trunc);
        if (!out) {
            throw std::runtime_error(
                "cannot create temporary model input file");
        }
        out.write(
            content.data(),
            static_cast<std::streamsize>(content.size()));
        if (!out) {
            throw std::runtime_error(
                "cannot write temporary model input file");
        }
    }

#ifndef _WIN32
    std::filesystem::permissions(
        path,
        std::filesystem::perms::owner_read |
            std::filesystem::perms::owner_write,
        std::filesystem::perm_options::replace);
#endif
}

std::string read_bounded(
    const std::filesystem::path& path,
    std::size_t max_bytes,
    bool keep_tail = false) {
    std::ifstream in(path, std::ios::binary);
    if (!in) return {};

    in.seekg(0, std::ios::end);
    const auto raw_size = in.tellg();
    if (raw_size < 0) return {};

    const std::size_t size =
        static_cast<std::size_t>(raw_size);
    if (size > max_bytes && !keep_tail) {
        throw std::runtime_error(
            "model output exceeded configured byte limit");
    }

    std::size_t read_size = std::min(size, max_bytes);
    std::size_t start = 0;
    if (keep_tail && size > read_size) {
        start = size - read_size;
    }

    in.seekg(
        static_cast<std::streamoff>(start),
        std::ios::beg);
    std::string result(read_size, '\0');
    in.read(
        result.data(),
        static_cast<std::streamsize>(read_size));
    result.resize(
        static_cast<std::size_t>(in.gcount()));
    return result;
}

std::string numeric(double value) {
    std::ostringstream out;
    out.precision(8);
    out << value;
    return out.str();
}

} // namespace

void validate_llama_cli_config(
    const LlamaCliConfig& c) {
    if (c.executable.empty()) {
        throw std::invalid_argument(
            "llama-cli executable path must be non-empty");
    }
    if (c.model_path.empty()) {
        throw std::invalid_argument(
            "math model path must be non-empty");
    }
    if (c.json_schema_path.empty()) {
        throw std::invalid_argument(
            "JSON schema path must be non-empty");
    }
    if (c.chat_template.empty()) {
        throw std::invalid_argument(
            "chat template must be non-empty");
    }
    if (c.max_tokens <= 0) {
        throw std::invalid_argument(
            "max_tokens must be positive");
    }
    if (!std::isfinite(c.temperature) ||
        c.temperature < 0.0 ||
        c.temperature > 2.0) {
        throw std::invalid_argument(
            "temperature must be finite and within [0,2]");
    }
    if (!std::isfinite(c.top_p) ||
        c.top_p <= 0.0 ||
        c.top_p > 1.0) {
        throw std::invalid_argument(
            "top_p must be finite and within (0,1]");
    }
    if (c.timeout_seconds <= 0) {
        throw std::invalid_argument(
            "timeout_seconds must be positive");
    }
    if (c.max_output_bytes == 0U ||
        c.max_diagnostic_bytes == 0U) {
        throw std::invalid_argument(
            "model byte limits must be positive");
    }
}

LlamaCliBackend::LlamaCliBackend(
    LlamaCliConfig config)
    : config_(std::move(config)) {
    validate_llama_cli_config(config_);
}

const LlamaCliConfig&
LlamaCliBackend::config() const noexcept {
    return config_;
}

TextGenerationResult LlamaCliBackend::generate(
    const TextGenerationRequest& request) {
    if (request.user_prompt.empty()) {
        return TextGenerationResult{
            .ok = false,
            .exit_code = 2,
            .timed_out = false,
            .output = {},
            .diagnostics = "user prompt must be non-empty",
        };
    }

#ifdef _WIN32
    return TextGenerationResult{
        .ok = false,
        .exit_code = 126,
        .timed_out = false,
        .output = {},
        .diagnostics =
            "LlamaCliBackend process isolation is not implemented on Windows yet",
    };
#else
    const auto base =
        std::filesystem::temp_directory_path() /
        ("expert-robot-qwen-" + unique_suffix());
    std::filesystem::create_directories(base);
    std::filesystem::permissions(
        base,
        std::filesystem::perms::owner_all,
        std::filesystem::perm_options::replace);

    const auto system_file = base / "system.txt";
    const auto prompt_file = base / "prompt.txt";
    const auto output_file = base / "output.json";
    const auto log_file = base / "llama.log";

    try {
        write_private_file(
            system_file,
            request.system_prompt);
        write_private_file(
            prompt_file,
            request.user_prompt);

        std::vector<std::string> args = {
            config_.executable.string(),
            "-m",
            std::filesystem::absolute(
                config_.model_path).string(),
            "-f",
            std::filesystem::absolute(
                prompt_file).string(),
            "-sysf",
            std::filesystem::absolute(
                system_file).string(),
            "-st",
            "--chat-template",
            config_.chat_template,
            "-n",
            std::to_string(config_.max_tokens),
            "--temp",
            numeric(config_.temperature),
            "--top-p",
            numeric(config_.top_p),
            "-s",
            std::to_string(config_.seed),
            "--simple-io",
            "--no-display-prompt",
            "--no-show-timings",
            "-co",
            "off",
            "-jf",
            std::filesystem::absolute(
                config_.json_schema_path).string(),
            "-o",
            std::filesystem::absolute(
                output_file).string(),
        };

        std::vector<char*> argv;
        argv.reserve(args.size() + 1U);
        for (auto& arg : args) {
            argv.push_back(arg.data());
        }
        argv.push_back(nullptr);

        const pid_t pid = fork();
        if (pid < 0) {
            throw std::runtime_error(
                "fork failed for llama-cli");
        }

        if (pid == 0) {
            const int fd = open(
                log_file.c_str(),
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

        int status = 0;
        bool timed_out = false;
        const auto deadline =
            std::chrono::steady_clock::now() +
            std::chrono::seconds(
                config_.timeout_seconds);

        while (true) {
            const pid_t result =
                waitpid(pid, &status, WNOHANG);
            if (result == pid) break;
            if (result < 0) break;

            if (std::chrono::steady_clock::now() >=
                deadline) {
                timed_out = true;
                kill(pid, SIGKILL);
                waitpid(pid, &status, 0);
                break;
            }

            std::this_thread::sleep_for(
                std::chrono::milliseconds(25));
        }

        int exit_code = 1;
        if (timed_out) {
            exit_code = 124;
        } else if (WIFEXITED(status)) {
            exit_code = WEXITSTATUS(status);
        } else if (WIFSIGNALED(status)) {
            exit_code = 128 + WTERMSIG(status);
        }

        std::string output;
        try {
            output = read_bounded(
                output_file,
                config_.max_output_bytes,
                false);
        } catch (const std::exception& e) {
            std::filesystem::remove_all(base);
            return TextGenerationResult{
                .ok = false,
                .exit_code = exit_code,
                .timed_out = timed_out,
                .output = {},
                .diagnostics = e.what(),
            };
        }

        std::string diagnostics =
            read_bounded(
                log_file,
                config_.max_diagnostic_bytes,
                true);

        std::filesystem::remove_all(base);

        const bool ok =
            !timed_out &&
            exit_code == 0 &&
            !output.empty();

        return TextGenerationResult{
            .ok = ok,
            .exit_code = exit_code,
            .timed_out = timed_out,
            .output = std::move(output),
            .diagnostics = std::move(diagnostics),
        };
    } catch (...) {
        std::filesystem::remove_all(base);
        throw;
    }
#endif
}

} // namespace expert_robot
