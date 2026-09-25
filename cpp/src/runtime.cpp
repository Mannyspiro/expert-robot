#include "expert_robot/runtime.hpp"

#include <cctype>
#include <sstream>
#include <string>

namespace expert_robot {
namespace {

bool extract_json_string(const std::string& line, const std::string& key, std::string& out) {
    const std::string needle = "\"" + key + "\"";
    const auto key_pos = line.find(needle);
    if (key_pos == std::string::npos) {
        return false;
    }

    const auto colon = line.find(':', key_pos + needle.size());
    if (colon == std::string::npos) {
        return false;
    }

    auto pos = line.find('"', colon + 1);
    if (pos == std::string::npos) {
        return false;
    }
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

} // namespace

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (const char ch : value) {
        switch (ch) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (static_cast<unsigned char>(ch) < 0x20U) {
                    out << '?';
                } else {
                    out << ch;
                }
        }
    }
    return out.str();
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

Response Runtime::handle(const Request& request) const {
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

    response.ok = true;
    response.result =
        "runtime accepted task for role '" + request.role +
        "'; model backend not connected yet";
    return response;
}

} // namespace expert_robot
