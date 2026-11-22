#pragma once

#include <string>

namespace expert_robot {

struct Request {
    std::string id;
    std::string role;
    std::string task;
    std::string payload;
};

struct Response {
    std::string id;
    bool ok{false};
    std::string result;
    std::string error;
};

std::string json_escape(const std::string& value);
bool parse_request_line(const std::string& line, Request& out, std::string& error);
std::string serialize_response(const Response& response);

} // namespace expert_robot
