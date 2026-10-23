cmake_minimum_required(VERSION 3.16)
project(finance_engine VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(finance_engine src/engine.cpp)
target_include_directories(finance_engine PUBLIC include third_party)
if(MSVC)
    target_compile_options(finance_engine PRIVATE /W4)
else()
    target_compile_options(finance_engine PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(engine_cli src/main.cpp)
target_link_libraries(engine_cli PRIVATE finance_engine)
add_executable(engine_tests tests/test_engine.cpp)
target_link_libraries(engine_tests PRIVATE finance_engine)

if(MINGW)
    target_link_options(engine_cli PRIVATE -static)
    target_link_options(engine_tests PRIVATE -static)
endif()

enable_testing()
add_test(NAME engine_tests COMMAND engine_tests)
