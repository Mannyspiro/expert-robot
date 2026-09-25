#include "expert_robot/runtime.hpp"

#include <iostream>
#include <string>

int main() {
    expert_robot::Runtime runtime;
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
