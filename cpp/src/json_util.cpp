#include "expert_robot/json_util.hpp"

#include <cctype>
#include <fstream>
#include <sstream>
#include <stdexcept>

namespace expert_robot::json_util {
namespace {

std::size_t find_key(const std::string& json, std::string_view key) {
    const std::string needle = "\"" + std::string(key) + "\"";
    const auto pos = json.find(needle);
    if (pos == std::string::npos) {
        return pos;
    }
    return json.find(':', pos + needle.size());
}

std::string parse_string_at(const std::string& text, std::size_t quote) {
    if (quote >= text.size() || text[quote] != '"') {
        throw std::invalid_argument("expected JSON string");
    }
    std::string out;
    bool escaped = false;
    for (std::size_t i = quote + 1U; i < text.size(); ++i) {
        const char ch = text[i];
        if (escaped) {
            switch (ch) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                default: out.push_back(ch); break;
            }
            escaped = false;
        } else if (ch == '\\') {
            escaped = true;
        } else if (ch == '"') {
            return out;
        } else {
            out.push_back(ch);
        }
    }
    throw std::invalid_argument("unterminated JSON string");
}

std::size_t matching_delimiter(const std::string& text, std::size_t start, char open, char close) {
    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t i = start; i < text.size(); ++i) {
        const char ch = text[i];
        if (in_string) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') in_string = false;
            continue;
        }
        if (ch == '"') {
            in_string = true;
            continue;
        }
        if (ch == open) ++depth;
        if (ch == close) {
            --depth;
            if (depth == 0) return i;
        }
    }
    throw std::invalid_argument("unbalanced JSON delimiter");
}

} // namespace

std::string escape(std::string_view value) {
    std::ostringstream out;
    for (unsigned char ch : value) {
        switch (ch) {
            case '"': out << "\\\""; break;
            case '\\': out << "\\\\"; break;
            case '\b': out << "\\b"; break;
            case '\f': out << "\\f"; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default:
                if (ch < 0x20U) {
                    const char* hex = "0123456789abcdef";
                    out << "\\u00" << hex[(ch >> 4U) & 0xfU] << hex[ch & 0xfU];
                } else {
                    out << static_cast<char>(ch);
                }
        }
    }
    return out.str();
}

std::string read_file(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open JSON file: " + path);
    }
    std::ostringstream buffer;
    buffer << in.rdbuf();
    return buffer.str();
}

std::vector<std::string> object_array(const std::string& json, std::string_view key) {
    const auto colon = find_key(json, key);
    if (colon == std::string::npos) return {};
    const auto start = json.find('[', colon + 1U);
    if (start == std::string::npos) throw std::invalid_argument("JSON field is not an array");
    const auto end = matching_delimiter(json, start, '[', ']');

    std::vector<std::string> objects;
    bool in_string = false;
    bool escaped = false;
    int depth = 0;
    std::size_t object_start = std::string::npos;
    for (std::size_t i = start + 1U; i < end; ++i) {
        const char ch = json[i];
        if (in_string) {
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') in_string = false;
            continue;
        }
        if (ch == '"') { in_string = true; continue; }
        if (ch == '{') {
            if (depth == 0) object_start = i;
            ++depth;
        } else if (ch == '}') {
            --depth;
            if (depth == 0 && object_start != std::string::npos) {
                objects.push_back(json.substr(object_start, i - object_start + 1U));
                object_start = std::string::npos;
            }
        }
    }
    return objects;
}

std::string string_field(const std::string& object, std::string_view key, const std::string& fallback) {
    const auto colon = find_key(object, key);
    if (colon == std::string::npos) return fallback;
    const auto quote = object.find('"', colon + 1U);
    if (quote == std::string::npos) return fallback;
    return parse_string_at(object, quote);
}

int int_field(const std::string& object, std::string_view key, int fallback) {
    const auto colon = find_key(object, key);
    if (colon == std::string::npos) return fallback;
    std::size_t pos = colon + 1U;
    while (pos < object.size() && std::isspace(static_cast<unsigned char>(object[pos]))) ++pos;
    std::size_t end = pos;
    if (end < object.size() && (object[end] == '-' || object[end] == '+')) ++end;
    while (end < object.size() && std::isdigit(static_cast<unsigned char>(object[end]))) ++end;
    if (end == pos) return fallback;
    return std::stoi(object.substr(pos, end - pos));
}

std::vector<std::string> string_array_field(const std::string& object, std::string_view key) {
    const auto colon = find_key(object, key);
    if (colon == std::string::npos) return {};
    const auto start = object.find('[', colon + 1U);
    if (start == std::string::npos) return {};
    const auto end = matching_delimiter(object, start, '[', ']');

    std::vector<std::string> values;
    for (std::size_t pos = start + 1U; pos < end;) {
        while (pos < end && (std::isspace(static_cast<unsigned char>(object[pos])) || object[pos] == ',')) ++pos;
        if (pos >= end) break;
        if (object[pos] != '"') throw std::invalid_argument("expected string array item");
        values.push_back(parse_string_at(object, pos));
        ++pos;
        bool escaped = false;
        while (pos < end) {
            const char ch = object[pos++];
            if (escaped) escaped = false;
            else if (ch == '\\') escaped = true;
            else if (ch == '"') break;
        }
    }
    return values;
}

} // namespace expert_robot::json_util
