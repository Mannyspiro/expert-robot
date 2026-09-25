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
    cpp/src/formalizer.cpp
    cpp/src/lemma_factory.cpp
    cpp/src/text_generation.cpp
    cpp/src/model_server.cpp
    cpp/src/model_lemma_decomposer.cpp
    cpp/src/swarm/task.cpp
    cpp/src/swarm/agent.cpp
    cpp/src/swarm/supervisor.cpp
    cpp/src/swarm/aggregator.cpp
    cpp/src/imagination/idea.cpp
    cpp/src/imagination/archive.cpp
    cpp/src/imagination/memory.cpp
    cpp/src/imagination/controller.cpp
    cpp/src/skills/math_skill.cpp
    cpp/src/skills/skill_ledger.cpp
    cpp/src/skills/experimental_skill_store.cpp
    cpp/src/skills/model_skill_proposer.cpp
    cpp/src/eval/math_eval.cpp
    cpp/src/research/state_machine.cpp
    cpp/src/research/episode_ledger.cpp
    cpp/src/cognition/neuromodulation.cpp
    cpp/src/cognition/interoception.cpp
    cpp/src/cognition/personality.cpp
    cpp/src/cognition/controller.cpp
    cpp/src/cognition/lemma_factory_bridge.cpp
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

add_executable(cognition_controller_smoke
    tests/cognition_controller_smoke.cpp
)
target_link_libraries(cognition_controller_smoke PRIVATE expert_robot_core)
add_test(NAME cognition_controller_smoke COMMAND cognition_controller_smoke)

add_executable(lemma_factory_smoke
    tests/lemma_factory_smoke.cpp
)
target_link_libraries(lemma_factory_smoke PRIVATE expert_robot_core)
add_test(NAME lemma_factory_smoke COMMAND lemma_factory_smoke)

add_executable(hybrid_math_engine_smoke
    tests/hybrid_math_engine_smoke.cpp
)
target_link_libraries(hybrid_math_engine_smoke PRIVATE expert_robot_core)
add_test(NAME hybrid_math_engine_smoke COMMAND hybrid_math_engine_smoke)

add_executable(growth_governance_smoke
    tests/growth_governance_smoke.cpp
)
target_link_libraries(growth_governance_smoke PRIVATE expert_robot_core)
add_test(NAME growth_governance_smoke COMMAND growth_governance_smoke)

add_executable(math_eval_smoke
    tests/math_eval_smoke.cpp
)
target_link_libraries(math_eval_smoke PRIVATE expert_robot_core)
add_test(NAME math_eval_smoke COMMAND math_eval_smoke)

add_executable(skill_growth_smoke
    tests/skill_growth_smoke.cpp
)
target_link_libraries(skill_growth_smoke PRIVATE expert_robot_core)
add_test(NAME skill_growth_smoke COMMAND skill_growth_smoke)

add_executable(research_state_machine_smoke
    tests/research_state_machine_smoke.cpp
)
target_link_libraries(research_state_machine_smoke PRIVATE expert_robot_core)
add_test(NAME research_state_machine_smoke COMMAND research_state_machine_smoke)

add_executable(research_episode_ledger_smoke
    tests/research_episode_ledger_smoke.cpp
)
target_link_libraries(research_episode_ledger_smoke PRIVATE expert_robot_core SQLite::SQLite3)
add_test(NAME research_episode_ledger_smoke COMMAND research_episode_ledger_smoke)
