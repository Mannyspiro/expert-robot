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

include(CTest)
if(BUILD_TESTING)
  add_executable(expert_robot_conformal_smoke tests/conformal_geometry_smoke.cpp)
  target_include_directories(expert_robot_conformal_smoke PRIVATE cpp/include)
  if(MSVC)
    target_compile_options(expert_robot_conformal_smoke PRIVATE /W4 /permissive-)
  else()
    target_compile_options(expert_robot_conformal_smoke PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wshadow)
  endif()
  add_test(NAME conformal_integer_identity COMMAND expert_robot_conformal_smoke)
endif()
