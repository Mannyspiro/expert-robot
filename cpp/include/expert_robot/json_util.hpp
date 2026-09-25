#pragma once

#include <string>
#include <string_view>
#include <vector>

namespace expert_robot::json_util {

[[nodiscard]] std::string escape(std::string_view value);
[[nodiscard]] std::string escape_ascii(std::string_view value);
[[nodiscard]] std::string read_file(const std::string& path);
[[nodiscard]] std::vector<std::string> object_array(const std::string& json, std::string_view key);
[[nodiscard]] std::string string_field(const std::string& object, std::string_view key, const std::string& fallback = "");
[[nodiscard]] int int_field(const std::string& object, std::string_view key, int fallback);
[[nodiscard]] std::vector<std::string> string_array_field(const std::string& object, std::string_view key);

} // namespace expert_robot::json_util
