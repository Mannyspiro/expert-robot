#include "expert_robot/proof_search.hpp"
#include "expert_robot/json_util.hpp"

#include <array>
#include <atomic>
#include <chrono>
#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <thread>

#ifndef _WIN32
#include <csignal>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace expert_robot {
namespace {

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return {};
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1U);
}

bool safe_tactic_fragment(std::string_view tactic) {
    if (tactic.empty() ||
        tactic.find('\n') != std::string_view::npos ||
        tactic.find('\r') != std::string_view::npos ||
        tactic.find('#') != std::string_view::npos) {
        return false;
    }

    const std::array<std::string_view, 5> forbidden = {
        "sorry",
        "admit",
        "axiom",
        "unsafe",
        "set_option",
    };

    for (const auto token : forbidden) {
        if (tactic.find(token) != std::string_view::npos) {
            return false;
        }
    }
    return true;
}


std::string read_text(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    std::ostringstream out;
    out << in.rdbuf();
    return out.str();
}

std::string unique_suffix() {
    static std::atomic<unsigned long long> counter{0};
    const auto ticks = std::chrono::steady_clock::now().time_since_epoch().count();
    return std::to_string(ticks) + "-" + std::to_string(counter.fetch_add(1));
}

} // namespace

LeanSubprocessRunner::LeanSubprocessRunner(std::filesystem::path root, int timeout_seconds)
    : root_(std::move(root)), timeout_seconds_(timeout_seconds) {
    if (timeout_seconds_ <= 0) {
        throw std::invalid_argument("timeout_seconds must be positive");
    }
}

LeanRunResult LeanSubprocessRunner::run(std::string_view source) {
#ifdef _WIN32
    throw std::runtime_error("LeanSubprocessRunner process isolation is not implemented on Windows yet");
#else
    const auto build_dir = root_ / "build" / "proof-search";
    std::filesystem::create_directories(build_dir);
    const auto suffix = unique_suffix();
    const auto candidate = std::filesystem::absolute(build_dir / ("candidate-" + suffix + ".lean"));
    const auto output = std::filesystem::absolute(build_dir / ("candidate-" + suffix + ".log"));

    {
        std::ofstream out(candidate, std::ios::binary | std::ios::trunc);
        if (!out) throw std::runtime_error("cannot create Lean proof-search candidate");
        out.write(source.data(), static_cast<std::streamsize>(source.size()));
    }

    const pid_t pid = fork();
    if (pid < 0) {
        std::filesystem::remove(candidate);
        throw std::runtime_error("fork failed for Lean proof search");
    }

    if (pid == 0) {
        const int fd = open(output.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0600);
        if (fd < 0) _exit(126);
        dup2(fd, STDOUT_FILENO);
        dup2(fd, STDERR_FILENO);
        close(fd);

        if (chdir(root_.c_str()) != 0) _exit(126);
        execlp("lake", "lake", "env", "lean", candidate.c_str(), static_cast<char*>(nullptr));
        _exit(127);
    }

    int status = 0;
    bool timed_out = false;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(timeout_seconds_);
    while (true) {
        const pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) break;
        if (result < 0) break;
        if (std::chrono::steady_clock::now() >= deadline) {
            timed_out = true;
            kill(pid, SIGKILL);
            waitpid(pid, &status, 0);
            break;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }

    std::string captured = read_text(output);
    std::filesystem::remove(candidate);
    std::filesystem::remove(output);

    if (timed_out) {
        captured += "\nTIMEOUT";
        return {124, std::move(captured)};
    }
    if (WIFEXITED(status)) {
        return {WEXITSTATUS(status), std::move(captured)};
    }
    if (WIFSIGNALED(status)) {
        return {128 + WTERMSIG(status), std::move(captured)};
    }
    return {1, std::move(captured)};
#endif
}

ProofSearchConfig load_proof_search_config(const std::filesystem::path& path) {
    const std::string json = json_util::read_file(path.string());
    if (json_util::int_field(json, "schema_version", -1) != 1) {
        throw std::invalid_argument("unsupported proof search schema_version");
    }

    ProofSearchConfig config;
    config.strategies = json_util::string_array_field(json, "strategies");
    config.timeout_seconds = json_util::int_field(json, "timeout_seconds", 20);
    if (config.strategies.empty()) {
        throw std::invalid_argument("proof search strategies must be a non-empty list of strings");
    }
    if (config.timeout_seconds <= 0) {
        throw std::invalid_argument("timeout_seconds must be positive");
    }
    return config;
}

DeterministicProofSearch::DeterministicProofSearch(
    std::vector<std::string> strategies,
    ILeanRunner& runner)
    : runner_(runner) {
    for (auto& strategy : strategies) {
        strategy = trim(std::move(strategy));
        if (!strategy.empty()) strategies_.push_back(std::move(strategy));
    }
    if (strategies_.empty()) {
        throw std::invalid_argument("proof search requires at least one deterministic strategy");
    }
}

std::string DeterministicProofSearch::render(const SearchProblem& problem, std::string_view tactic) {
    std::ostringstream out;
    for (const auto& module : problem.imports) {
        out << "import " << module << "\n";
    }
    for (const auto& declaration : problem.context_declarations) {
        out << "\n" << declaration << "\n";
    }
    out << "\ntheorem " << problem.candidate_name << " " << problem.statement << " := by\n"
        << "  " << tactic << "\n";
    return out.str();
}

SearchResult DeterministicProofSearch::search(const SearchProblem& problem) {
    SearchResult result;
    result.problem = problem;

    std::vector<std::string> tactics;
    tactics.reserve(
        problem.preferred_strategies.size() +
        strategies_.size());

    auto append_unique_safe =
        [&](std::string tactic) {
            tactic = trim(std::move(tactic));
            if (tactic.empty()) return;
            if (!safe_tactic_fragment(tactic)) {
                throw std::invalid_argument(
                    "preferred proof tactic contains a forbidden fragment");
            }
            if (std::find(
                    tactics.begin(),
                    tactics.end(),
                    tactic) == tactics.end()) {
                tactics.push_back(
                    std::move(tactic));
            }
        };

    for (const auto& tactic :
         problem.preferred_strategies) {
        append_unique_safe(tactic);
    }
    for (const auto& tactic :
         strategies_) {
        append_unique_safe(tactic);
    }

    for (const auto& tactic : tactics) {
        auto run = runner_.run(render(problem, tactic));
        const bool success = run.exit_code == 0;
        result.attempts.push_back(SearchAttempt{
            .tactic = tactic,
            .success = success,
            .exit_code = run.exit_code,
            .output = std::move(run.output),
        });
        if (success) {
            result.success = true;
            result.tactic = tactic;
            result.proof = "by\n  " + tactic;
            return result;
        }
    }
    return result;
}

} // namespace expert_robot
