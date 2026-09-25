cmake_minimum_required(VERSION 3.20)
project(expert_robot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(SQLite3 REQUIRED)
find_package(Threads REQUIRED)

add_library(expert_robot_core STATIC
    cpp/src/runtime.cpp
    cpp/src/capabilities.cpp
    cpp/src/sha256.cpp
    cpp/src/json_util.cpp
    cpp/src/proof_search.cpp
    cpp/src/proof_memory.cpp
    cpp/src/knowledge_graph.cpp
    cpp/src/cognition/neuromodulation.cpp
    cpp/src/cognition/interoception.cpp
    cpp/src/cognition/personality.cpp
)

target_include_directories(expert_robot_core PUBLIC cpp/include)
target_link_libraries(expert_robot_core PRIVATE SQLite::SQLite3 Threads::Threads)

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

add_executable(math_core_smoke
    tests/math_core_smoke.cpp
)
target_link_libraries(math_core_smoke PRIVATE expert_robot_core)
add_test(NAME math_core_smoke COMMAND math_core_smoke)

add_executable(neuromodulation_smoke
    tests/neuromodulation_smoke.cpp
)
target_link_libraries(neuromodulation_smoke PRIVATE expert_robot_core)
add_test(NAME neuromodulation_smoke COMMAND neuromodulation_smoke)

add_executable(interoception_smoke
    tests/interoception_smoke.cpp
)
target_link_libraries(interoception_smoke PRIVATE expert_robot_core)
add_test(NAME interoception_smoke COMMAND interoception_smoke)

add_executable(personality_smoke
    tests/personality_smoke.cpp
)
target_link_libraries(personality_smoke PRIVATE expert_robot_core)
add_test(NAME personality_smoke COMMAND personality_smoke)
