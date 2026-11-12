#include "expert_robot/runtime.hpp"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <string>

int main() {
    const char* configured_db = std::getenv("MERLIN_ARTIFACT_DB");
    const std::filesystem::path artifact_db =
        configured_db && *configured_db
            ? std::filesystem::path(configured_db)
            : std::filesystem::path("state/merlin/artifacts.sqlite3");
    expert_robot::Runtime runtime(artifact_db);
    std::string line;

    while (std::getline(std::cin, line)) {
        if (line.empty()) {
            continue;
        }

        expert_robot::Request request;
        std::string error;
        if (!expert_robot::parse_request_line(line, request, error)) {
            expert_robot::Response response;
            response.id = "";
            response.ok = false;
            response.error = error;
            std::cout << expert_robot::serialize_response(response) << std::endl;
            continue;
        }

        std::cout << expert_robot::serialize_response(runtime.handle(request)) << std::endl;
    }

    return 0;
}
