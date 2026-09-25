cmake_minimum_required(VERSION 3.20)
project(expert_robot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(expert_robot_core STATIC
    cpp/src/runtime.cpp
    cpp/src/capabilities.cpp
)

target_include_directories(expert_robot_core PUBLIC cpp/include)

if(MSVC)
  target_compile_options(expert_robot_core PRIVATE /W4 /permissive-)
else()
  target_compile_options(expert_robot_core PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
endif()

add_executable(expert_robot_runtime
    cpp/src/main.cpp
)
target_link_libraries(expert_robot_runtime PRIVATE expert_robot_core)

enable_testing()

add_executable(capabilities_smoke
    tests/capabilities_smoke.cpp
)
target_link_libraries(capabilities_smoke PRIVATE expert_robot_core)

add_test(NAME capabilities_smoke COMMAND capabilities_smoke)
