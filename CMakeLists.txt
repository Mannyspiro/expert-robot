cmake_minimum_required(VERSION 3.20)
project(expert_robot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(expert_robot_runtime
    cpp/src/main.cpp
    cpp/src/runtime.cpp
)

target_include_directories(expert_robot_runtime PRIVATE cpp/include)

if(MSVC)
  target_compile_options(expert_robot_runtime PRIVATE /W4 /permissive-)
else()
  target_compile_options(expert_robot_runtime PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
endif()
